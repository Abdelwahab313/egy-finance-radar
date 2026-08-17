"""Single-ticker investigation agent.

Two layers:
  1. `analyze_ticker(symbol)` — pure, deterministic. Reuses the existing engine
     (fetch -> metrics -> classify -> score -> signal) for ONE symbol, fetched
     alongside the full universe so beta has a market proxy and we can rank the
     target against its peers. No network beyond yfinance; no LLM.
  2. `investigate(symbol)` — orchestrator. Precomputes (1) to a JSON context
     file, then spawns headless Claude Code (`claude -p`) driving the
     `stock-investigator` subagent to web-research the name and `Write` a
     markdown report to data/reports/SYMBOL_DATE.md.

CLI:  python -m app.agent.investigator --analyze SYMBOL   (prints the JSON)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from datetime import date, datetime, timezone

from app import config
from app.analysis import classifier, metrics, signals
from app.data.sources import MarksOverlaySource, YFinanceSource
from app.data.universe import EGX_UNIVERSE, symbols

# backend/ — investigator.py lives at backend/app/agent/investigator.py
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS_DIR = os.path.join(BACKEND_DIR, config.REPORTS_DIR)
CTX_DIR = os.path.join(REPORTS_DIR, ".ctx")
LOG_DIR = os.path.join(REPORTS_DIR, ".log")

# in-memory job registry for status polling (background execution)
JOBS: dict[str, dict] = {}

# peer-comparison metrics we summarise vs the universe
PEER_FIELDS = ["score", "pe", "pb", "dividend_yield", "roe", "beta", "volatility"]


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.endswith(".CA"):
        s = s[:-3]
    return s


def _peer_comparison(target: dict, peers: list[dict]) -> dict:
    """Target vs universe: percentile rank on score + bucket-median key metrics."""
    valid = [p for p in peers if p["metrics"].get("data_ok")]
    scores = sorted(p["score"] for p in valid)
    t_score = target["score"]
    pctile = (sum(1 for s in scores if s < t_score) / len(scores)) if scores else None

    def _median(vals):
        vals = [v for v in vals if isinstance(v, (int, float))]
        return round(statistics.median(vals), 4) if vals else None

    bucket = target["bucket"]
    same_bucket = [p for p in valid if p["bucket"] == bucket]
    bucket_medians = {
        f: _median([(p["score"] if f == "score" else p["metrics"].get(f)) for p in same_bucket])
        for f in PEER_FIELDS
    }
    universe_medians = {
        f: _median([(p["score"] if f == "score" else p["metrics"].get(f)) for p in valid])
        for f in PEER_FIELDS
    }
    return {
        "universe_size": len(valid),
        "score_percentile": round(pctile, 3) if pctile is not None else None,
        "target_bucket": bucket,
        "bucket_peer_count": len(same_bucket),
        "bucket_medians": bucket_medians,
        "universe_medians": universe_medians,
        "ranked": [{"symbol": p["symbol"], "bucket": p["bucket"], "score": p["score"]}
                   for p in sorted(valid, key=lambda p: p["score"], reverse=True)],
    }


def _position_block(sym: str, target_price: float | None) -> dict | None:
    """Build the held-Position context block for ``sym`` from the DB, or ``None``
    if the symbol isn't held (no ``position`` row / no orders).

    Aggregates that symbol's buy/sell ``orders`` into shares + cost basis (weighted
    -average entry), reads the owner-intended ``horizon`` from the ``position`` row,
    and marks to ``target_price`` (the live price from the deterministic analysis)
    for market value / unrealized P&L. DB connection hygiene is the caller's job
    (``investigate`` wraps connect/close); the CLI path opens its own.
    """
    from app.db import connect
    from app.db.models import Orders, Position

    connect()
    pos = Position.get_or_none(Position.symbol == sym)
    if pos is None:
        return None

    rows = list(Orders.select().where(Orders.symbol == sym).order_by(Orders.id))
    if not rows:
        return None

    shares = 0.0
    cost_total = 0.0
    for row in rows:
        s = float(row.shares)
        signed = s if row.side == "buy" else -s
        shares += signed
        cost_total += signed * float(row.price)

    avg_entry_price = round(cost_total / shares, 4) if shares else None
    mkt = round((target_price or avg_entry_price or 0.0) * shares, 2)
    pnl = round(mkt - cost_total, 2)
    return {
        "horizon": pos.horizon,
        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        "shares": round(shares, 4),
        "cost_basis_total": round(cost_total, 2),
        "avg_entry_price": avg_entry_price,
        "market_value": mkt,
        "unrealized_pnl": pnl,
        "unrealized_pct": round(pnl / cost_total, 4) if cost_total else None,
    }


def analyze_ticker(symbol: str) -> dict:
    """Deterministic quantitative analysis of one symbol vs the EGX universe."""
    sym = normalize_symbol(symbol)
    universe = symbols()
    to_fetch = [sym] + [u for u in universe if u != sym]

    # Overlay owner marks (ADR-0006). Without this the investigation report is
    # written off the vendor's last published bar — which on 17-Aug-2026 meant
    # every source quoting ABUK at 73.71 while the broker showed 79.70.
    fetch = MarksOverlaySource(YFinanceSource()).fetch(to_fetch)
    index_rets, index_source = metrics.market_returns(fetch)

    def _one(s: str) -> dict:
        ph = fetch.prices.get(s)
        if ph is None:  # symbol absent (shouldn't happen — we fetched it)
            from app.data.sources import PriceHistory
            import pandas as pd
            ph = PriceHistory(s, pd.DataFrame(), ok=False, error="not fetched")
        computed = metrics.compute_metrics(ph, index_rets)
        merged = metrics.merge_fundamentals(
            static=EGX_UNIVERSE.get(s, {}).get("fundamentals", {}),
            live=fetch.live_info.get(s, {}),
            computed=computed,
        )
        eligible, gate_fails = classifier.passes_gates(merged)
        return {
            "symbol": s,
            "name": EGX_UNIVERSE.get(s, {}).get("name"),
            "sector": EGX_UNIVERSE.get(s, {}).get("sector"),
            "eligible": eligible,
            "gate_fails": gate_fails,
            "bucket": classifier.classify(merged),
            "score": classifier.quality_score(merged),
            "metrics": merged,
            "signal": signals.compute_signal(ph.df),
        }

    target = _one(sym)
    peers = [_one(u) for u in universe if u != sym]

    m = target["metrics"]
    return {
        "symbol": sym,
        "as_of": date.today().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "in_universe": sym in EGX_UNIVERSE,
        "position": _position_block(sym, m.get("price")),
        "target": target,
        "peers": _peer_comparison(target, [target] + peers),
        "data_quality": {
            "price_data_ok": bool(m.get("data_ok")),
            "beta_source": index_source,
            "provenance": m.get("provenance", {}),
            "mostly_static_fields": sorted(
                f for f, src in (m.get("provenance") or {}).items() if src == "static"
            ),
            "caveat": ("yfinance gives reliable PRICES for EGX but unreliable/absent "
                       "fundamentals. Fields with static provenance are curated "
                       "June-2026 figures, not a live feed. Treat fundamentals as "
                       "directional and validate against web research."),
        },
    }


# --- orchestration -----------------------------------------------------------

def _report_paths(sym: str, day: str) -> tuple[str, str, str, str, str]:
    filename = f"{sym}_{day}.md"
    return (
        filename,
        os.path.join(REPORTS_DIR, filename),
        os.path.join(CTX_DIR, f"{sym}_{day}.json"),
        os.path.join(LOG_DIR, f"{sym}_{day}.log"),
        os.path.join(CTX_DIR, f"{sym}_{day}.reco.json"),
    )


def _horizon_framing(position: dict | None) -> str:
    """The Horizon-specific instruction block injected into the prompt.

    Core = judge the long-term thesis; Tactical = near-term catalysts + price
    target + stop; not-held = today's general framing. In all held cases, anchor
    the agent to the owner's actual cost basis / P&L rather than a fresh entry.
    """
    if position is None:
        return (
            "This symbol is NOT a current holding — there is no Position. Frame the report as a "
            "general entry analysis for a prospective buyer, using the technical levels in the JSON.\n"
        )

    basis = (
        f"The owner ALREADY HOLDS this Position: {position['shares']} shares at a weighted-average "
        f"entry of {position['avg_entry_price']} EGP (cost basis {position['cost_basis_total']} EGP), "
        f"current unrealized P&L {position['unrealized_pnl']} EGP "
        f"({position['unrealized_pct']}). Reason about the OWNER'S actual P&L from this entry, "
        f"not a fresh entry. Full details are in the JSON `position` block.\n"
    )
    if position["horizon"] == "core":
        return basis + (
            "Horizon = CORE (long-term hold). Judge whether the LONG-TERM THESIS still holds: "
            "fundamentals, durable competitive moat, and the multi-quarter outlook. Frame the "
            "recommendation around thesis intact / impaired, not short-term price wiggles.\n"
        )
    return basis + (
        "Horizon = TACTICAL (short-term hold). Focus on NEAR-TERM catalysts and news, a concrete "
        "PRICE TARGET, and a STOP-LOSS, using the technical levels (entry zone, stop-loss, "
        "take-profit, supports/resistances) in the JSON.\n"
    )


def _build_prompt(sym: str, ctx_path: str, report_path: str, reco_path: str,
                  day: str, position: dict | None) -> str:
    return (
        f"Investigate the Egyptian Exchange (EGX) listed share **{sym}** and write a full "
        f"analyst report. Today is {day}.\n\n"
        f"A precomputed deterministic analysis (prices, returns, volatility, beta, bucket "
        f"classification, quality score, technical signal, peer comparison vs the EGX universe, "
        f"and — if held — a `position` block with the owner's Horizon and cost basis) has ALREADY "
        f"been written to:\n  {ctx_path}\n\n"
        f"{_horizon_framing(position)}\n"
        f"Steps:\n"
        f"1. `Read` that JSON. Use its numbers as the source of truth for all quantitative "
        f"claims — do NOT invent or recompute prices/metrics. Note its data_quality caveats "
        f"(which fields are live vs curated static fallbacks). If a `position` block is present, "
        f"weigh it per the Horizon framing above.\n"
        f"2. Web-research the company with WebSearch/WebFetch: what it does, recent news/results, "
        f"current macro/sector scene, and how it compares to the peers listed in the JSON. "
        f"Cite every web claim with its source URL.\n"
        f"3. Validate the data: flag anything implausible or stale; say plainly where you could "
        f"not verify a number.\n"
        f"4. Lay out concrete entry/exit options using the technical levels in the JSON "
        f"(entry zone, stop-loss, take-profit, supports/resistances).\n"
        f"5. Give a clear decision & recommendation with reasoning.\n\n"
        f"`Write` your prose report as a single markdown file to EXACTLY this path:\n  {report_path}\n\n"
        f"Then ALSO `Write` a machine-readable JSON sidecar to EXACTLY this path "
        f"(create nothing else beyond these two files):\n  {reco_path}\n"
        f"The sidecar MUST conform to this schema exactly:\n"
        f'{{\n'
        f'  "symbol": "{sym}",\n'
        f'  "as_of": "{day}",\n'
        f'  "horizon": "core|tactical",   // ALWAYS one of these two; pick based on your framing\n'
        f'  "action": "hold|add|trim|sell",\n'
        f'  "rationale": "1-3 sentence verdict",\n'
        f'  "price_target": 0.0,   // EGP, or null\n'
        f'  "stop_loss": 0.0,      // EGP, or null\n'
        f'  "news": [\n'
        f'    {{"headline": "...", "url": "...", "source": "...", "published_at": "YYYY-MM-DD or null", "summary": "..."}}\n'
        f'  ]\n'
        f'}}\n'
        f"Emit a VALID `horizon` (core or tactical) even when the symbol is not held. Populate "
        f"`news` from the dated, URL-cited items you researched (empty array if none).\n\n"
        f"Follow the section structure from your agent instructions. This is research/education "
        f"only, not investment advice — include that disclaimer in the markdown report."
    )


_VALID_ACTIONS = {"hold", "add", "trim", "sell"}
_VALID_HORIZONS = {"core", "tactical"}


def _store_recommendation(sym: str, day: str, horizon: str | None,
                          report_file: str, sidecar: dict) -> dict | None:
    """Persist one structured Recommendation (+ its News rows) to Postgres from an
    already-parsed sidecar dict. Standalone + DB-only so it is testable without the
    LLM and reusable by Step 5's Refresh pass.

    ``horizon`` is AUTHORITATIVE — pass the held Position's horizon (``'core'`` /
    ``'tactical'``). When given, it overrides whatever the agent guessed; the
    sidecar's own ``horizon`` is only a sanity check (a mismatch is logged). When
    ``None`` (symbol not held), we fall back to the sidecar's horizon, then
    ``'tactical'`` to satisfy the recommendation.horizon CHECK.

    Inserts each ``news[]`` item (capturing ids), then one ``recommendation`` row
    whose ``news_ids`` links them. ``action`` is validated against the allowed CHECK
    values; an invalid action aborts the insert (returns ``None``). Returns the
    inserted row as a dict, or ``None`` on any problem (logged, never raised — so a
    bad sidecar never fails the surrounding investigation). The caller owns DB
    connect/close.
    """
    from app.db.models import News, Recommendation

    try:
        as_of = day or sidecar.get("as_of") or date.today().isoformat()
        sidecar_horizon = str(sidecar.get("horizon") or "").lower()
        # DB Position horizon wins when held; sidecar is a sanity check only.
        if horizon in _VALID_HORIZONS:
            if sidecar_horizon and sidecar_horizon != horizon:
                print(f"[ingest] horizon mismatch for {sym}: DB={horizon!r} "
                      f"sidecar={sidecar_horizon!r}; using DB value")
            final_horizon = horizon
        else:
            final_horizon = sidecar_horizon if sidecar_horizon in _VALID_HORIZONS else "tactical"

        action = str(sidecar.get("action") or "").lower()
        if action not in _VALID_ACTIONS:
            print(f"[ingest] invalid action {action!r} for {sym}; no reco persisted")
            return None

        news_ids: list[int] = []
        for item in (sidecar.get("news") or []):
            if not isinstance(item, dict) or not item.get("headline"):
                continue
            row = News.create(
                symbol=sym,
                headline=str(item["headline"]),
                url=item.get("url"),
                source=item.get("source"),
                published_at=(item.get("published_at") or None),
                summary=item.get("summary"),
            )
            news_ids.append(row.id)

        reco = Recommendation.create(
            symbol=sym,
            as_of=as_of,
            horizon=final_horizon,
            action=action,
            rationale=sidecar.get("rationale"),
            price_target=sidecar.get("price_target"),
            stop_loss=sidecar.get("stop_loss"),
            news_ids=news_ids,
            report_file=report_file,
        )
        print(f"[ingest] recommendation {reco.id} for {sym} ({action}/{final_horizon}) "
              f"with {len(news_ids)} news row(s)")
        return {"id": reco.id, "symbol": sym, "as_of": as_of, "horizon": final_horizon,
                "action": action, "news_ids": news_ids, "report_file": report_file}
    except Exception as exc:  # noqa: BLE001 — never crash the report on a bad sidecar
        print(f"[ingest] failed to persist reco for {sym}: {exc}")
        return None


def _ingest_recommendation(sym: str, day: str, horizon: str | None,
                           report_file: str, sidecar_path: str) -> dict | None:
    """Read the agent's structured ``.reco.json`` sidecar from disk and persist it
    via :func:`_store_recommendation`. Returns ``None`` (logged, never raised) if the
    sidecar is missing or malformed, so the prose report still counts as done.

    ``horizon`` is the held Position's horizon (authoritative) or ``None`` if the
    symbol is not held.
    """
    if not os.path.exists(sidecar_path):
        print(f"[ingest] no sidecar at {sidecar_path}; no structured reco persisted")
        return None
    try:
        with open(sidecar_path) as f:
            sidecar = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ingest] malformed sidecar {sidecar_path}: {exc}; no structured reco persisted")
        return None
    return _store_recommendation(sym, day, horizon, report_file, sidecar)


def investigate(symbol: str, force: bool = False) -> dict:
    """Precompute deterministic analysis, then run the headless agent to write the report."""
    sym = normalize_symbol(symbol)
    day = date.today().isoformat()
    filename, report_path, ctx_path, log_path, reco_path = _report_paths(sym, day)

    if os.path.exists(report_path) and not force:
        JOBS[filename] = {"status": "done", "error": None, "started": None}
        return {"filename": filename, "symbol": sym, "date": day,
                "status": "done", "cached": True, "report_path": report_path}

    JOBS[filename] = {"status": "running", "error": None,
                      "started": datetime.now(timezone.utc).isoformat()}

    from app.db import close as db_close, connect as db_connect

    try:
        # 1. deterministic analysis -> .ctx JSON (agent input). analyze_ticker reads
        # the Position from the DB; wrap the whole DB-touching span in connect/close
        # since this runs in a FastAPI BackgroundTask (step-3 hygiene pattern).
        os.makedirs(CTX_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(REPORTS_DIR, exist_ok=True)
        db_connect()
        analysis = analyze_ticker(sym)
        position = analysis.get("position")
        with open(ctx_path, "w") as f:
            json.dump(analysis, f, indent=2, default=str)

        # 2. headless Claude Code drives the stock-investigator subagent
        prompt = _build_prompt(sym, ctx_path, report_path, reco_path, day, position)
        cmd = [
            config.CLAUDE_BIN, "-p", prompt,
            "--agent", "stock-investigator",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "WebSearch", "WebFetch(domain:*)",
            "Bash(python3 *)", "Read", "Write",
            "--model", config.INVESTIGATE_MODEL,
            "--max-turns", str(config.INVESTIGATE_MAX_TURNS),
            "--output-format", "text",
        ]
        proc = subprocess.run(
            cmd, cwd=BACKEND_DIR, capture_output=True, text=True,
            timeout=config.INVESTIGATE_TIMEOUT_S,
        )
        with open(log_path, "w") as f:
            f.write(f"$ {' '.join(cmd[:1])} -p <prompt> {' '.join(cmd[3:])}\n")
            f.write(f"\n--- exit code: {proc.returncode} ---\n")
            f.write("\n--- stdout ---\n" + (proc.stdout or ""))
            f.write("\n--- stderr ---\n" + (proc.stderr or ""))

        # 3. verify the agent actually wrote the report
        if not os.path.exists(report_path):
            msg = (f"agent finished (exit {proc.returncode}) but no report was written. "
                   f"See log: {log_path}")
            JOBS[filename] = {"status": "error", "error": msg, "started": None}
            return {"filename": filename, "symbol": sym, "date": day,
                    "status": "error", "error": msg}

        # 4. ingest the structured reco sidecar (best-effort; never blocks "done").
        # Horizon is taken from the held Position (authoritative); the agent's
        # sidecar horizon is only a sanity check. None when the symbol isn't held.
        held_horizon = position.get("horizon") if position else None
        reco = _ingest_recommendation(sym, day, held_horizon, filename, reco_path)

        JOBS[filename] = {"status": "done", "error": None, "started": None}
        return {"filename": filename, "symbol": sym, "date": day,
                "status": "done", "cached": False, "report_path": report_path,
                "recommendation_stored": reco is not None,
                "recommendation": reco}

    except FileNotFoundError:
        msg = (f"'{config.CLAUDE_BIN}' CLI not found on PATH. Install Claude Code and log in.")
        JOBS[filename] = {"status": "error", "error": msg, "started": None}
        return {"filename": filename, "symbol": sym, "date": day, "status": "error", "error": msg}
    except subprocess.TimeoutExpired as exc:
        # surface whatever the agent produced before the kill, for debugging
        try:
            with open(log_path, "w") as f:
                f.write(f"--- TIMEOUT after {config.INVESTIGATE_TIMEOUT_S}s ---\n")
                f.write("\n--- stdout ---\n" + (exc.stdout or ""))
                f.write("\n--- stderr ---\n" + (exc.stderr or ""))
        except OSError:
            pass
        msg = f"investigation timed out after {config.INVESTIGATE_TIMEOUT_S}s."
        JOBS[filename] = {"status": "error", "error": msg, "started": None}
        return {"filename": filename, "symbol": sym, "date": day, "status": "error", "error": msg}
    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
        msg = f"investigation failed: {exc}"
        JOBS[filename] = {"status": "error", "error": msg, "started": None}
        return {"filename": filename, "symbol": sym, "date": day, "status": "error", "error": msg}
    finally:
        # BackgroundTask worker thread — don't leave the peewee connection dangling.
        db_close()


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="EGX single-ticker investigator")
    ap.add_argument("--analyze", metavar="SYMBOL",
                    help="print deterministic analysis JSON for SYMBOL and exit")
    ap.add_argument("--investigate", metavar="SYMBOL",
                    help="run the full headless investigation (writes a report)")
    ap.add_argument("--force", action="store_true", help="re-run even if today's report exists")
    args = ap.parse_args(argv)

    if args.analyze:
        print(json.dumps(analyze_ticker(args.analyze), indent=2, default=str))
        return 0
    if args.investigate:
        print(json.dumps(investigate(args.investigate, force=args.force), indent=2, default=str))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
