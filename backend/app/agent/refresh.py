"""The Refresh runner — the one-button background job (ADR-0002).

A Refresh:
  1. ``collect()`` + ``save()`` — re-fetch the universe, recompute metrics, and
     regenerate the ``snapshot.json`` cache (unchanged behaviour; this also
     re-marks held-order prices).
  2. **History append** (then the ADR-0007 scorecard pass) — for every computed stock, upsert a ``price_history``
     row ``(symbol, as_of=today, close)`` and a ``metric_snapshot`` row
     ``(symbol, as_of=today, bucket, score, metrics, signal)``. The
     ``UNIQUE(symbol, as_of)`` constraint + ``on_conflict`` make a same-day
     re-run idempotent (overwrite, never duplicate). Values come from the
     ``stocks`` list ``collect()`` already computed — nothing is re-fetched.
  3. **Recommendation pass** — for EVERY held ``Position`` **and every symbol in
     ``config.INVESTIGATE_WATCHLIST``**, force-run the headless investigator so a
     fresh structured ``recommendation`` (+ ``news``) is stored. Per ADR-0002 this
     is intentionally expensive and runs sequentially; the watchlist is the
     owner's bounded exception to ADR-0004 (see that ADR's 04-Aug-2026 amendment),
     so its length is a direct multiplier on Refresh cost.

The LLM pass (step 3) is deliberately a separate, individually-callable piece
guarded by ``run_recommendations`` so steps 1–2 (price/metric history) work and
are verifiable WITHOUT spending tokens.

DB hygiene: this runs on a FastAPI background thread, so we ``connect()`` once at
the top and ``close()`` in a ``finally`` (the step-3 pattern).
"""

from __future__ import annotations

import shutil
import threading
from datetime import date, datetime, timezone

from app import config


def _claude_available() -> bool:
    """Is the headless ``claude`` CLI on PATH? It is on the host (where it's
    logged in) but NOT in the backend container — so the recommendation pass runs
    on the host (reaching Postgres via the localhost:5433 mapping), while the
    container's Refresh does the deterministic half only."""
    return shutil.which(config.CLAUDE_BIN) is not None


# Coarse, in-memory, single-process status the /api/refresh/status endpoint reads.
# Mirrors the investigator's JOBS pattern.
STATUS: dict = {
    "status": "idle",      # idle | running | done | error
    "started": None,
    "finished": None,
    "steps": {},           # phase + counts
    "error": None,
}

# Guard against concurrent refreshes (single-process app).
_LOCK = threading.Lock()
_RUNNING = False


def is_running() -> bool:
    return _RUNNING


def try_begin() -> bool:
    """Atomically claim the single-flight slot. Returns True if the caller now owns
    the refresh (and MUST call ``run_refresh``), False if one is already in flight.

    Called synchronously from the request handler BEFORE scheduling the background
    task, so back-to-back POSTs are rejected even before the task thread starts.
    """
    global _RUNNING
    if not _LOCK.acquire(blocking=False):
        return False
    _RUNNING = True
    STATUS.update({
        "status": "running",
        "started": datetime.now(timezone.utc).isoformat(),
        "finished": None,
        "error": None,
        "steps": {"phase": "queued"},
    })
    return True


def _set_phase(phase: str, **extra) -> None:
    STATUS["steps"]["phase"] = phase
    STATUS["steps"].update(extra)


def _append_history(stocks: list[dict], as_of: date) -> dict:
    """Upsert price_history + metric_snapshot rows for the day from already-computed
    ``stocks``. Idempotent per ``(symbol, as_of)`` via ON CONFLICT. Returns counts.

    Only symbols that exist in ``instrument`` are written (FK safety); a computed
    symbol with no instrument row is skipped and counted.
    """
    from app.db import db
    from app.db.models import Instrument, MetricSnapshot, PriceHistory

    known = {row[0] for row in Instrument.select(Instrument.symbol).tuples()}

    price_rows = 0
    metric_rows = 0
    skipped: list[str] = []
    for s in stocks:
        sym = s["symbol"]
        if sym not in known:
            skipped.append(sym)
            continue
        m = s.get("metrics") or {}
        close = m.get("price")

        (PriceHistory
         .insert(symbol=sym, as_of=as_of, close=close)
         .on_conflict(
             conflict_target=[PriceHistory.symbol, PriceHistory.as_of],
             preserve=[PriceHistory.close],
         )
         .execute())
        price_rows += 1

        (MetricSnapshot
         .insert(symbol=sym, as_of=as_of, bucket=s.get("bucket"),
                 score=s.get("score"), metrics=m, signal=s.get("signal") or {})
         .on_conflict(
             conflict_target=[MetricSnapshot.symbol, MetricSnapshot.as_of],
             preserve=[MetricSnapshot.bucket, MetricSnapshot.score,
                       MetricSnapshot.metrics, MetricSnapshot.signal],
         )
         .execute())
        metric_rows += 1

    return {"price_history_upserts": price_rows,
            "metric_snapshot_upserts": metric_rows,
            "skipped_unknown_symbols": skipped}


def _run_recommendation_pass() -> dict:
    """Force-run the headless investigator over every held Position **plus every
    ``config.INVESTIGATE_WATCHLIST`` symbol**, sequentially.

    Each Position's owner-intended horizon flows through ``investigate`` ->
    ``_ingest_recommendation`` (authoritative horizon), so the stored row's
    horizon matches the Position. Watchlist symbols are not held, so they carry no
    Position horizon — ``investigate`` falls back to the sidecar's own horizon and
    then to 'tactical'. Held names run first; a watchlist name that is also held is
    investigated once. Per-symbol success/failure is collected; one bad symbol
    never aborts the rest. Returns a per-symbol result map + counts.

    Separated from the history step so the expensive/slow LLM work is an
    individually-callable seam.
    """
    from app.agent.investigator import investigate
    from app.db.models import Position

    held = [p.symbol_id for p in Position.select().order_by(Position.symbol)]
    watch = [s for s in config.INVESTIGATE_WATCHLIST if s not in set(held)]
    symbols = held + watch
    total = len(symbols)
    results: dict[str, dict] = {}
    ok = 0
    for i, sym in enumerate(symbols, start=1):
        _set_phase(f"recommendations: {i}/{total} ({sym})",
                   recommendations_total=total, recommendations_done=i - 1)
        try:
            res = investigate(sym, force=True)
            success = res.get("status") == "done"
            results[sym] = {
                "status": res.get("status"),
                "recommendation_stored": res.get("recommendation_stored"),
                "error": res.get("error"),
            }
            if success:
                ok += 1
        except Exception as exc:  # noqa: BLE001 — one bad symbol must not abort the pass
            results[sym] = {"status": "error", "error": str(exc)}
        _set_phase(f"recommendations: {i}/{total} ({sym})",
                   recommendations_total=total, recommendations_done=i)
    return {"positions": len(held), "watchlist": len(watch), "total": total,
            "succeeded": ok, "per_symbol": results}


def run_refresh(run_recommendations: bool = True, source=None) -> dict:
    """Execute a full Refresh. Designed to be called from a FastAPI BackgroundTask.

    ``run_recommendations=False`` runs ONLY the price/metric-history part (collect +
    snapshot + history upsert) and SKIPS the expensive LLM pass — used by
    verification and any cheap "data-only" refresh.

    Owns its DB connection (connect at top, close in finally) since it runs on a
    background thread. Updates the module-level ``STATUS`` as it progresses.
    """
    global _RUNNING

    # The HTTP handler claims the slot via try_begin() before scheduling us; a
    # direct call (verification/CLI) claims it here. Either way we hold _LOCK.
    claimed_here = False
    if not _RUNNING:
        if not _LOCK.acquire(blocking=False):
            return {"status": "already_running"}
        _RUNNING = True
        claimed_here = True
        STATUS.update({
            "status": "running",
            "started": datetime.now(timezone.utc).isoformat(),
            "finished": None,
            "error": None,
        })

    from app.agent.collector import collect, save
    from app.db import close as db_close, connect as db_connect

    today = date.today()
    STATUS["steps"] = {"phase": "starting", "run_recommendations": run_recommendations}
    summary: dict = {"status": "running"}
    try:
        db_connect()

        # 1. collect + snapshot cache (also re-marks held-order prices).
        _set_phase("collecting")
        snap = collect(source=source)
        save(snap)
        summary["generated_at"] = snap["generated_at"]
        summary["live_data_ok_count"] = snap["live_data_ok_count"]

        # 2. append price/metric history (idempotent upsert).
        _set_phase("history")
        summary["history"] = _append_history(snap["stocks"], today)

        # 2b. score every past verdict against realised closes (ADR-0007). A
        # scoring failure is recorded and must not block the recommendation pass.
        _set_phase("scorecard")
        try:
            from app.analysis import scorecard
            summary["scorecard"] = scorecard.score_all(source=source, today=today)
        except Exception as exc:  # noqa: BLE001
            summary["scorecard"] = {"error": str(exc)}

        # 3. force-run the recommendation pass over every held Position. The pass
        # shells out to the headless `claude` CLI, which only exists on the host —
        # so in the container (no claude) we skip it cleanly rather than failing
        # per-symbol. Run `python -m app.agent.refresh` on the host for the real
        # recommendation pass (it reaches Postgres via the localhost:5433 mapping).
        if run_recommendations and not _claude_available():
            _set_phase("recommendations: skipped (claude unavailable — run "
                       "`python -m app.agent.refresh` on the host)")
            summary["recommendations"] = {
                "skipped": True,
                "reason": "claude CLI not on PATH (LLM pass is a host-run job)",
            }
        elif run_recommendations:
            summary["recommendations"] = _run_recommendation_pass()
        else:
            _set_phase("recommendations: skipped")
            summary["recommendations"] = {"skipped": True}

        _set_phase("done")
        STATUS["status"] = "done"
        summary["status"] = "done"
    except Exception as exc:  # noqa: BLE001 — surface to the status endpoint
        STATUS["status"] = "error"
        STATUS["error"] = str(exc)
        summary["status"] = "error"
        summary["error"] = str(exc)
    finally:
        STATUS["finished"] = datetime.now(timezone.utc).isoformat()
        db_close()
        _RUNNING = False
        _LOCK.release()
    return summary


def _main(argv: list[str]) -> int:
    """Host CLI: run a full Refresh from the host, where the `claude` CLI is logged
    in. Reaches Postgres via DATABASE_URL (defaults to the localhost:5433 mapping).

        python -m app.agent.refresh                 # full pass incl. recommendations
        python -m app.agent.refresh --no-recommendations   # deterministic only
    """
    import argparse
    import json

    ap = argparse.ArgumentParser(description="EGX Refresh runner (host job)")
    ap.add_argument("--no-recommendations", action="store_true",
                    help="run only the price/metric-history pass; skip the LLM pass")
    args = ap.parse_args(argv)

    if not args.no_recommendations and not _claude_available():
        print("[refresh] warning: `claude` CLI not found on PATH — the "
              "recommendation pass will be skipped. Run this on the host where "
              "Claude Code is installed and logged in.")
    result = run_refresh(run_recommendations=not args.no_recommendations)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "done" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
