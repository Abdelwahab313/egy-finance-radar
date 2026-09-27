"""FastAPI app serving the cached snapshot to the Next.js dashboard.

Endpoints:
  GET /api/health      -> liveness
  GET /api/snapshot    -> full snapshot (scene, stocks, shortlist, portfolio)
  GET /api/stocks      -> classified stocks only
  GET /api/portfolio   -> portfolio only
  POST /api/refresh    -> re-run the collection agent (slow; hits yfinance)
  POST /api/investigate          -> kick off a single-ticker investigation (background)
  GET  /api/investigate/status   -> poll a running investigation
  GET  /api/reports              -> list past investigation reports
  GET  /api/reports/{filename}   -> fetch one report's markdown
  GET  /api/recommendations      -> stored structured verdicts for a symbol (newest-first)
  GET  /api/scorecard            -> realised outcome of every verdict + hit rates (ADR-0007)
"""

from __future__ import annotations

import glob
import json
import os
import re

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config

app = FastAPI(title="egy-finance-radar API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load() -> dict:
    if not os.path.exists(config.SNAPSHOT_PATH):
        raise HTTPException(503, "No snapshot yet — run `python -m app.agent.collector`.")
    with open(config.SNAPSHOT_PATH) as f:
        return json.load(f)


@app.get("/api/health")
def health():
    return {"status": "ok", "snapshot_exists": os.path.exists(config.SNAPSHOT_PATH)}


@app.get("/api/snapshot")
def snapshot():
    return _load()


@app.get("/api/stocks")
def stocks():
    return {"stocks": _load()["stocks"]}


@app.get("/api/portfolio")
def portfolio():
    s = _load()
    return {"portfolio": s["portfolio"], "starting_capital_egp": s["starting_capital_egp"]}


@app.get("/api/signals")
def signals():
    s = _load()
    return {
        "generated_at": s["generated_at"],
        "per_stock": {st["symbol"]: st.get("signal") for st in s["stocks"]},
        "portfolio_actions": s["portfolio"].get("actions", []),
    }


@app.post("/api/refresh")
def refresh(background: BackgroundTasks):
    """Kick off a Refresh as a BACKGROUND job (ADR-0002): re-fetch prices/metrics,
    append price/metric history, then force-re-run the LLM recommendation pass over
    every held Position, and regenerate the snapshot cache. Returns immediately;
    poll ``GET /api/refresh/status`` for progress. A second call while one is in
    flight returns ``{"status": "already_running"}`` (in-process guard)."""
    from app.agent.refresh import STATUS, run_refresh, try_begin

    # Claim the single-flight slot synchronously so a second POST is rejected even
    # before the background task thread starts running.
    if not try_begin():
        return {"status": "already_running", "started": STATUS.get("started")}
    background.add_task(run_refresh)
    return {"status": "running", "started": STATUS.get("started")}


@app.get("/api/refresh/status")
def refresh_status():
    """Coarse, in-memory progress of the most recent/current Refresh:
    ``{status: idle|running|done|error, started, finished, steps:{phase,...}, error}``."""
    from app.agent.refresh import STATUS
    return STATUS


# --- Orders: log a new placed lot from the dashboard -------------------------

class OrderRequest(BaseModel):
    symbol: str
    shares: float
    entry_price: float
    as_of: str | None = None
    side: str = "buy"
    traded_at: str | None = None
    horizon: str | None = None


@app.post("/api/orders")
def add_order(req: OrderRequest):
    """Persist a new user-placed lot, fetch a live price for it, re-mark all
    holdings, and write the refreshed holdings block back into the snapshot."""
    from datetime import date

    if not SYMBOL_RE.match(req.symbol):
        raise HTTPException(400, "Invalid symbol — expected 1–8 alphanumeric characters.")
    if req.shares <= 0:
        raise HTTPException(400, "shares must be positive.")
    if req.entry_price <= 0:
        raise HTTPException(400, "entry_price must be positive.")
    if req.side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'.")
    if req.horizon is not None and req.horizon not in ("core", "tactical"):
        raise HTTPException(400, "horizon must be 'core' or 'tactical'.")

    from app.agent.collector import add_order as record_order, save
    from app.db import close as db_close
    sym = req.symbol.strip().upper()
    if sym.endswith(".CA"):
        sym = sym[:-3]
    as_of = req.as_of or date.today().isoformat()

    try:
        holdings = record_order(sym, req.shares, req.entry_price, as_of,
                                side=req.side, traded_at=req.traded_at,
                                horizon=req.horizon)
    finally:
        # peewee connections aren't threadsafe across requests/tasks — don't leave
        # this request's connection dangling on the worker thread.
        db_close()

    # patch the live holdings block into the cached snapshot so the dashboard
    # reflects the new lot without a full (slow) collector re-run.
    if os.path.exists(config.SNAPSHOT_PATH):
        snap = _load()
        snap["holdings"] = holdings
        save(snap)

    return {"status": "added", "symbol": sym, "holdings": holdings}


# --- Stock investigation agent + report viewer -------------------------------

SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,8}$")
REPORT_FILENAME_RE = re.compile(r"^[A-Z0-9]+_\d{4}-\d{2}-\d{2}\.md$")


class InvestigateRequest(BaseModel):
    symbol: str
    force: bool = False


@app.post("/api/investigate")
def investigate(req: InvestigateRequest, background: BackgroundTasks):
    from app.agent.investigator import (
        JOBS, investigate as run_investigate, normalize_symbol,
    )
    from datetime import date

    if not SYMBOL_RE.match(req.symbol):
        raise HTTPException(400, "Invalid symbol — expected 1–8 alphanumeric characters.")
    sym = normalize_symbol(req.symbol)
    day = date.today().isoformat()
    filename = f"{sym}_{day}.md"

    # If today's report already exists and not forcing, it's done immediately.
    if os.path.exists(os.path.join(_reports_dir(), filename)) and not req.force:
        return {"symbol": sym, "date": day, "filename": filename, "status": "done"}

    JOBS[filename] = {"status": "running", "error": None, "started": None}
    background.add_task(run_investigate, sym, req.force)
    return {"symbol": sym, "date": day, "filename": filename, "status": "running"}


@app.get("/api/investigate/status")
def investigate_status(filename: str):
    from app.agent.investigator import JOBS
    if not REPORT_FILENAME_RE.match(filename):
        raise HTTPException(400, "Invalid filename.")
    job = JOBS.get(filename)
    if os.path.exists(os.path.join(_reports_dir(), filename)):
        return {"status": "done"}
    if job:
        return {"status": job["status"], "error": job.get("error")}
    return {"status": "unknown"}


@app.get("/api/recommendations")
def recommendations(symbol: str | None = None):
    """Stored, structured verdicts newest-first (plan contract), optionally filtered
    by ``?symbol=SYM``. Omitting ``symbol`` returns every Position's recommendations."""
    sym = None
    if symbol is not None:
        if not SYMBOL_RE.match(symbol):
            raise HTTPException(400, "Invalid symbol — expected 1–8 alphanumeric characters.")
        sym = symbol.strip().upper()
        if sym.endswith(".CA"):
            sym = sym[:-3]

    from app.db import close as db_close, connect as db_connect
    from app.db.models import Recommendation
    try:
        db_connect()
        rows = (Recommendation
                .select()
                .order_by(Recommendation.as_of.desc(), Recommendation.id.desc()))
        if sym is not None:
            rows = rows.where(Recommendation.symbol == sym)
        return [{
            "symbol": r.symbol_id,
            "as_of": r.as_of.isoformat() if r.as_of else None,
            "horizon": r.horizon,
            "action": r.action,
            "rationale": r.rationale,
            "price_target": float(r.price_target) if r.price_target is not None else None,
            "stop_loss": float(r.stop_loss) if r.stop_loss is not None else None,
            "report_file": r.report_file,
        } for r in rows]
    finally:
        db_close()


@app.get("/api/scorecard")
def scorecard_view(symbol: str | None = None):
    """Realised outcome of every stored verdict plus hit rates (ADR-0007).
    Rows are upserted by the Refresh; this endpoint only reads."""
    sym = None
    if symbol is not None:
        if not SYMBOL_RE.match(symbol):
            raise HTTPException(400, "Invalid symbol — expected 1–8 alphanumeric characters.")
        sym = symbol.strip().upper()

    from app.analysis import scorecard
    from app.db import close as db_close, connect as db_connect
    try:
        db_connect()
        return scorecard.report(sym)
    finally:
        db_close()


@app.get("/api/reports")
def reports():
    out = []
    for path in glob.glob(os.path.join(_reports_dir(), "*.md")):
        fn = os.path.basename(path)
        if not REPORT_FILENAME_RE.match(fn):
            continue
        symbol, day = fn[:-3].split("_", 1)
        out.append({"symbol": symbol, "date": day, "filename": fn})
    out.sort(key=lambda r: (r["date"], r["symbol"]), reverse=True)
    return out


@app.get("/api/reports/{filename}")
def report(filename: str):
    if not REPORT_FILENAME_RE.match(filename):  # path-traversal guard
        raise HTTPException(400, "Invalid filename.")
    path = os.path.join(_reports_dir(), filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found.")
    with open(path) as f:
        return {"filename": filename, "markdown": f.read()}


def _reports_dir() -> str:
    from app.agent.investigator import REPORTS_DIR
    return REPORTS_DIR
