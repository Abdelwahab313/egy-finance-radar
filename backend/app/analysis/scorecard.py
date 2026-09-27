"""Score past Recommendations against realised closes (ADR-0007).

``score()`` is pure: one verdict, one close series, one evaluation date. The
DB-facing functions upsert an outcome row per recommendation and build the
summary the API serves. Callers own the DB connection.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

WINDOW_DAYS = {"tactical": 30, "core": 365}
ENTRY_MAX_GAP_DAYS = 7
LONG_ACTIONS = {"add", "hold"}
SHORT_ACTIONS = {"trim", "sell"}


def _f(v) -> float | None:
    return None if v is None else float(v)


def _to_dates(closes: pd.Series) -> pd.Series:
    s = closes.dropna()
    s.index = [i.date() if hasattr(i, "date") else i for i in s.index]
    return s.sort_index()


def score(reco: dict, closes: pd.Series | None, today: date | None = None) -> dict:
    """Evaluate one verdict. ``reco`` needs as_of (date), horizon, action,
    price_target, stop_loss. Returns the outcome columns as a dict."""
    today = today or date.today()
    as_of: date = reco["as_of"]
    window_days = WINDOW_DAYS[reco["horizon"]]
    window_end = as_of + timedelta(days=window_days)
    out = {
        "window_days": window_days, "window_end": window_end,
        "entry_date": None, "entry_price": None, "last_date": None, "last_price": None,
        "max_close": None, "min_close": None, "return_pct": None,
        "status": "no_data", "resolved_on": None, "correct": None,
    }
    if closes is None or closes.empty:
        return out
    s = _to_dates(closes)
    window = s[(s.index >= as_of) & (s.index <= window_end)]
    if window.empty or (window.index[0] - as_of).days > ENTRY_MAX_GAP_DAYS:
        return out

    entry = float(window.iloc[0])
    target = _f(reco.get("price_target"))
    stop = _f(reco.get("stop_loss"))
    status, resolved_on = None, None
    for d, close in window.items():
        c = float(close)
        if stop is not None and c <= stop:
            status, resolved_on = "stop_hit", d
            break
        if target is not None and c >= target:
            status, resolved_on = "target_hit", d
            break
    if status is None:
        if today > window_end:
            status, resolved_on = "expired", window.index[-1]
        else:
            status = "open"

    last = float(window.iloc[-1])
    ret = last / entry - 1.0
    action = reco["action"]
    correct = None
    if status == "target_hit":
        correct = action in LONG_ACTIONS
    elif status == "stop_hit":
        correct = action in SHORT_ACTIONS
    elif status == "expired":
        correct = ret > 0 if action in LONG_ACTIONS else ret < 0

    out.update({
        "entry_date": window.index[0], "entry_price": entry,
        "last_date": window.index[-1], "last_price": last,
        "max_close": float(window.max()), "min_close": float(window.min()),
        "return_pct": ret, "status": status, "resolved_on": resolved_on,
        "correct": correct,
    })
    return out


def _closes_from_price_history(symbol: str) -> pd.Series:
    from app.db.models import PriceHistory
    rows = (PriceHistory.select(PriceHistory.as_of, PriceHistory.close)
            .where((PriceHistory.symbol == symbol) & (PriceHistory.close.is_null(False)))
            .order_by(PriceHistory.as_of).tuples())
    data = {d: float(c) for d, c in rows}
    return pd.Series(data, dtype=float)


def load_closes(symbols: list[str], source=None) -> dict[str, pd.Series]:
    """Daily closes per symbol from the DataSource, price_history as fallback."""
    if not symbols:
        return {}
    if source is None:
        from app.data.sources import MarksOverlaySource, YFinanceSource
        source = MarksOverlaySource(YFinanceSource())
    fetch = source.fetch(symbols)
    out: dict[str, pd.Series] = {}
    for sym in symbols:
        ph = fetch.prices.get(sym)
        if ph is not None and ph.ok and not ph.df.empty and "Close" in ph.df:
            out[sym] = ph.df["Close"]
        else:
            out[sym] = _closes_from_price_history(sym)
    return out


def score_all(source=None, today: date | None = None) -> dict:
    """Upsert an outcome for every recommendation. Idempotent per recommendation."""
    from app.db.models import Recommendation, RecommendationOutcome

    recos = list(Recommendation.select().order_by(Recommendation.as_of, Recommendation.id))
    closes = load_closes(sorted({r.symbol_id for r in recos}), source)
    now = datetime.now(timezone.utc)
    by_status: dict[str, int] = {}
    for r in recos:
        o = score({
            "as_of": r.as_of, "horizon": r.horizon, "action": r.action,
            "price_target": r.price_target, "stop_loss": r.stop_loss,
        }, closes.get(r.symbol_id), today)
        by_status[o["status"]] = by_status.get(o["status"], 0) + 1
        values = {**o, "evaluated_at": now, "symbol": r.symbol_id}
        (RecommendationOutcome
         .insert(recommendation=r.id, **values)
         .on_conflict(
             conflict_target=[RecommendationOutcome.recommendation],
             update={getattr(RecommendationOutcome, k): v for k, v in values.items()},
         )
         .execute())
    return {"scored": len(recos), "by_status": by_status}


def _rate(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["correct"] is not None]
    correct = sum(1 for r in scored if r["correct"])
    return {
        "scored": len(scored), "correct": correct,
        "hit_rate": (correct / len(scored)) if scored else None,
    }


def report(symbol: str | None = None) -> dict:
    """Rows newest first plus hit rates overall, by horizon and by action."""
    from app.db.models import Recommendation, RecommendationOutcome

    q = (RecommendationOutcome
         .select(RecommendationOutcome, Recommendation)
         .join(Recommendation)
         .order_by(Recommendation.as_of.desc(), Recommendation.id.desc()))
    if symbol is not None:
        q = q.where(Recommendation.symbol == symbol)
    rows = []
    for o in q:
        r = o.recommendation
        rows.append({
            "recommendation_id": r.id, "symbol": r.symbol_id,
            "as_of": r.as_of.isoformat(), "horizon": r.horizon, "action": r.action,
            "price_target": _f(r.price_target), "stop_loss": _f(r.stop_loss),
            "window_end": o.window_end.isoformat(),
            "entry_price": _f(o.entry_price), "last_price": _f(o.last_price),
            "max_close": _f(o.max_close), "min_close": _f(o.min_close),
            "return_pct": _f(o.return_pct), "status": o.status,
            "resolved_on": o.resolved_on.isoformat() if o.resolved_on else None,
            "correct": o.correct,
            "evaluated_at": o.evaluated_at.isoformat() if isinstance(o.evaluated_at, datetime) else str(o.evaluated_at),
        })
    summary = {
        "overall": _rate(rows),
        "by_horizon": {h: _rate([r for r in rows if r["horizon"] == h]) for h in WINDOW_DAYS},
        "by_action": {a: _rate([r for r in rows if r["action"] == a])
                      for a in sorted(LONG_ACTIONS | SHORT_ACTIONS)},
        "unscored": sum(1 for r in rows if r["correct"] is None),
    }
    return {"summary": summary, "rows": rows}
