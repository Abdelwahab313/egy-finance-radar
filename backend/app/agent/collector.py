"""The collection agent: fetch EGX data -> compute metrics -> classify + score ->
shortlist -> build the 10k EGP balanced portfolio -> write a JSON snapshot the API serves.

Run:  python -m app.agent.collector
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from app import config
from app.analysis import classifier, metrics, signals
from app.data.sources import DataSource, YFinanceSource
from app.data.universe import EGX_UNIVERSE, symbols
from app.portfolio.account import build_portfolio

BUCKET_ORDER = ["stable_bluechip", "value", "growth", "watchlist", "speculative"]


def collect(source: DataSource | None = None) -> dict:
    source = source or YFinanceSource()
    syms = symbols()
    print(f"[agent] fetching {len(syms)} EGX symbols via {type(source).__name__} ...")
    fetch = source.fetch(syms)
    index_rets, index_source = metrics.market_returns(fetch)
    index_ok = index_rets is not None
    if index_source != "CASE30":
        print(f"[agent] EGX30 index unusable from source; beta uses '{index_source}'.")

    stocks = []
    live_ok = 0
    prov_counter: dict[str, dict[str, int]] = {}
    for sym in syms:
        profile = EGX_UNIVERSE[sym]
        ph = fetch.prices[sym]
        computed = metrics.compute_metrics(ph, index_rets)
        if computed.get("data_ok"):
            live_ok += 1
        merged = metrics.merge_fundamentals(
            static=profile["fundamentals"],
            live=fetch.live_info.get(sym, {}),
            computed=computed,
        )
        for field, src in (merged.get("provenance") or {}).items():
            prov_counter.setdefault(field, {}).setdefault(src, 0)
            prov_counter[field][src] += 1
        eligible, gate_fails = classifier.passes_gates(merged)
        bucket = classifier.classify(merged)
        score = classifier.quality_score(merged)
        signal = signals.compute_signal(ph.df)
        stocks.append({
            "symbol": sym,
            "name": profile["name"],
            "sector": profile["sector"],
            "eligible": eligible,
            "gate_fails": gate_fails,
            "bucket": bucket,
            "score": score,
            "metrics": merged,
            "signal": signal,
        })
        flag = "ok" if computed.get("data_ok") else "fallback"
        print(f"  {sym:6} {bucket:16} score={score:5}  [{flag}]")

    stocks.sort(key=lambda s: (BUCKET_ORDER.index(s["bucket"]) if s["bucket"]
                               in BUCKET_ORDER else 99, -s["score"]))

    # shortlist: eligible, non-speculative, NOT signalling EXIT/AVOID, top N by score.
    # Gating on the signal here is the fix for the book buying names it told you to
    # sell — the classifier/score path and the technical path now agree before a
    # position is ever sized.
    eligible_invest = [s for s in stocks if s["eligible"]
                       and s["bucket"] in config.TARGET_BUCKET_WEIGHTS
                       and (s["signal"].get("signal") not in config.BLOCK_SIGNALS)]
    eligible_invest.sort(key=lambda s: s["score"], reverse=True)
    shortlist = eligible_invest[: config.SHORTLIST_SIZE]
    excluded_by_signal = sorted(
        s["symbol"] for s in stocks
        if s["eligible"] and s["bucket"] in config.TARGET_BUCKET_WEIGHTS
        and s["signal"].get("signal") in config.BLOCK_SIGNALS)

    portfolio = build_portfolio(shortlist)

    # attach the entry/exit signal to each holding, tag its sleeve, summarise actions
    sig_by_sym = {s["symbol"]: s["signal"] for s in stocks}
    stock_by_sym = {s["symbol"]: s for s in stocks}
    actions = []
    net_div_income = 0.0
    for pos in portfolio.get("positions", []):
        sig = sig_by_sym.get(pos["symbol"], {"signal": "NO_DATA"})
        action = sig.get("signal")
        pos["signal"] = action
        pos["stop_loss"] = (sig.get("levels") or {}).get("stop_loss")
        pos["take_profit"] = (sig.get("levels") or {}).get("take_profit")
        # core = long-term hold (strong score + healthy trend); else tactical satellite
        pos["sleeve"] = ("core" if (pos.get("score", 0) >= config.CORE_SCORE_MIN
                                    and action in config.CORE_SIGNALS) else "satellite")
        dy = (stock_by_sym.get(pos["symbol"], {}).get("metrics") or {}).get("dividend_yield") or 0.0
        net_div_income += pos["notional"] * dy * (1.0 - config.DIV_WHT_PCT)
        actions.append({
            "symbol": pos["symbol"],
            "signal": action,
            "sleeve": pos["sleeve"],
            "reasons": sig.get("reasons", []),
            "stop_loss": pos["stop_loss"],
            "take_profit": pos["take_profit"],
        })
    portfolio["actions"] = actions
    portfolio["excluded_by_signal"] = excluded_by_signal
    portfolio["plan"] = _plan_block(portfolio, round(net_div_income, 2))

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": type(source).__name__,
        "index_source": index_source,
        "index_data_ok": index_ok,
        "price_data_ok_count": live_ok,
        "live_data_ok_count": live_ok,   # kept for back-compat
        "universe_size": len(syms),
        "data_quality": _data_quality(prov_counter, live_ok, len(syms), index_source),
        "starting_capital_egp": config.STARTING_CAPITAL_EGP,
        "scene": _scene_brief(),
        "stocks": stocks,
        "shortlist": [s["symbol"] for s in shortlist],
        "portfolio": portfolio,
        "holdings": _holdings_block({s["symbol"]: s for s in stocks}),
        "config": _config_brief(),
    }
    return snapshot


# Static holdings note (orders.json is demoted; this text was its `note`).
HOLDINGS_NOTE = ("User-placed core-sleeve orders. entry_price = price recorded at "
                 "order time; P&L is marked to the latest snapshot price.")


def _holdings_block(stock_by_sym: dict) -> dict | None:
    """Read user-placed orders from the Postgres ``orders`` table and mark them to
    the latest live prices, building the holdings JSON the frontend consumes.

    Each order row is its own lot (matching the prior orders.json behaviour where
    two COMI lots stayed two lots). A per-lot ``horizon`` is sourced from that
    symbol's ``position.horizon`` (or null if there's no position row). Name/sector
    prefer the live stock data, then the ``instrument`` table, then EGX_UNIVERSE.
    """
    from app.db import connect
    from app.db.models import Orders, Position

    connect()
    rows = list(Orders.select().order_by(Orders.id))
    if not rows:
        return None

    horizon_by_sym = {p.symbol_id: p.horizon for p in Position.select()}

    lots = []
    cost_total = mkt_total = 0.0
    max_traded_at = None
    for row in rows:
        sym = row.symbol_id
        if max_traded_at is None or row.traded_at > max_traded_at:
            max_traded_at = row.traded_at
        st = stock_by_sym.get(sym, {})
        name, sector = _instrument_meta(sym, st)
        price = (st.get("metrics") or {}).get("price")
        if price is None:                       # Yahoo can't price it (e.g. MTF fund)
            price = config.MANUAL_NAV.get(sym)  # → mark to manual NAV, not cost
        sig = st.get("signal") or {}
        entry = float(row.price)
        shares = float(row.shares)
        cost = entry * shares
        mkt = (price or entry) * shares
        pnl = mkt - cost
        cost_total += cost
        mkt_total += mkt
        lots.append({
            "symbol": sym,
            "name": name,
            "sector": sector,
            "shares": shares,
            "entry_price": entry,
            "price": price,
            "cost_basis": round(cost, 2),
            "market_value": round(mkt, 2),
            "unrealized_pnl": round(pnl, 2),
            "unrealized_pct": round(pnl / cost, 4) if cost else None,
            "signal": sig.get("signal"),
            "stop_loss": (sig.get("levels") or {}).get("stop_loss"),
            "take_profit": (sig.get("levels") or {}).get("take_profit"),
            "horizon": horizon_by_sym.get(sym),
        })
    pnl_total = mkt_total - cost_total
    return {
        "as_of": max_traded_at.isoformat() if max_traded_at else None,
        "note": HOLDINGS_NOTE,
        "lots": lots,
        "cost_basis_total": round(cost_total, 2),
        "market_value_total": round(mkt_total, 2),
        "unrealized_pnl_total": round(pnl_total, 2),
        "unrealized_pct_total": round(pnl_total / cost_total, 4) if cost_total else None,
        "deployed_pct_of_capital": round(cost_total / config.STARTING_CAPITAL_EGP, 4),
        "cash_uninvested": round(config.STARTING_CAPITAL_EGP - cost_total, 2),
    }


def _instrument_meta(symbol: str, st: dict) -> tuple[str | None, str | None]:
    """Resolve (name, sector): prefer live stock data, then the ``instrument``
    table, then EGX_UNIVERSE."""
    name = st.get("name")
    sector = st.get("sector")
    if name and sector:
        return name, sector
    from app.db.models import Instrument
    inst = Instrument.get_or_none(Instrument.symbol == symbol)
    if inst is not None:
        return name or inst.name, sector or inst.sector
    profile = EGX_UNIVERSE.get(symbol, {})
    return name or profile.get("name"), sector or profile.get("sector")


def add_order(symbol: str, shares: float, entry_price: float,
              as_of: str | None = None, side: str = "buy",
              traded_at: str | None = None, horizon: str | None = None) -> dict:
    """Insert a user-placed order into the Postgres ``orders`` table, then re-mark all
    lots to live prices. Returns the refreshed holdings block (also persisted into
    the snapshot by the caller).

    ``side`` ('buy'|'sell') and ``traded_at`` (the order date, falling back to
    ``as_of`` then today) are recorded on the order row. ``horizon``
    ('core'|'tactical') sets the Position's owner intent: a new Position uses
    ``horizon or 'core'``; an existing Position is UPDATEd only when a horizon is
    explicitly passed.

    Ensures FK integrity: if the symbol has no ``instrument`` row yet, a minimal one
    is created (name/sector from EGX_UNIVERSE if present, else name=symbol,
    sector='Unknown', in_universe=False)."""
    from datetime import date

    from app.db import connect, db
    from app.db.models import Instrument, Orders, Position

    order_date = (date.fromisoformat(traded_at) if traded_at
                  else date.fromisoformat(as_of) if as_of
                  else date.today())

    connect()
    with db.atomic():
        if Instrument.get_or_none(Instrument.symbol == symbol) is None:
            profile = EGX_UNIVERSE.get(symbol, {})
            Instrument.create(
                symbol=symbol,
                name=profile.get("name", symbol),
                sector=profile.get("sector", "Unknown"),
                in_universe=symbol in EGX_UNIVERSE,
            )
        Orders.create(
            symbol=symbol,
            side=side,
            shares=shares,
            price=entry_price,
            traded_at=order_date,
        )
        pos = Position.get_or_none(Position.symbol == symbol)
        if pos is None:
            Position.create(symbol=symbol, horizon=horizon or "core",
                            opened_at=order_date)
        elif horizon is not None and pos.horizon != horizon:
            pos.horizon = horizon
            pos.save()

    return mark_orders_to_live()


def mark_orders_to_live() -> dict | None:
    """Fetch fresh prices for ONLY the symbols held in the ``orders`` table and
    re-mark P&L, without re-running the full universe collection. Returns the
    holdings block."""
    from app.db import connect
    from app.db.models import Orders

    connect()
    order_syms = sorted(
        {row[0] for row in Orders.select(Orders.symbol).distinct().tuples()}
    )
    if not order_syms:
        return _holdings_block({})

    fetch = YFinanceSource().fetch(order_syms)
    index_rets, _ = metrics.market_returns(fetch)
    stock_by_sym: dict[str, dict] = {}
    for sym in order_syms:
        ph = fetch.prices.get(sym)
        profile = EGX_UNIVERSE.get(sym, {})
        computed = metrics.compute_metrics(ph, index_rets) if ph is not None else {}
        merged = metrics.merge_fundamentals(
            static=profile.get("fundamentals", {}),
            live=fetch.live_info.get(sym, {}),
            computed=computed,
        )
        stock_by_sym[sym] = {
            "symbol": sym,
            "name": profile.get("name"),
            "sector": profile.get("sector"),
            "metrics": merged,
            "signal": signals.compute_signal(ph.df) if ph is not None else {},
        }
    return _holdings_block(stock_by_sym)


def _data_quality(prov: dict, price_ok: int, universe: int, index_source: str) -> dict:
    """Honest summary of how much of the classification is live vs static fallback."""
    fields = {}
    for field, srcs in prov.items():
        live = srcs.get("computed", 0) + srcs.get("live", 0)
        fields[field] = {"live_or_computed": live, "static": srcs.get("static", 0)}
    static_driven = [f for f, c in fields.items()
                     if c["static"] > c["live_or_computed"]]
    return {
        "price_history": f"{price_ok}/{universe} symbols",
        "beta_source": index_source,
        "per_field": fields,
        "mostly_static_fields": sorted(static_driven),
        "caveat": ("yfinance gives reliable PRICES for EGX but unreliable/absent "
                   "fundamentals; fields listed in mostly_static_fields come from "
                   "curated June-2026 figures, not a live feed. Wire EODHD for live "
                   "fundamentals."),
    }


def _plan_block(portfolio: dict, net_div_income_egp: float) -> dict:
    """Turn the holdings into an investable plan: sleeves, cadence, sell rules,
    and the income the cash + equity sleeves are expected to throw off."""
    positions = portfolio.get("positions", [])
    core = [p["symbol"] for p in positions if p.get("sleeve") == "core"]
    satellite = [p["symbol"] for p in positions if p.get("sleeve") == "satellite"]
    tbill_income = portfolio.get("tbill_sleeve", {}).get("expected_annual_income_egp", 0.0)
    return {
        "sleeves": {
            "tbill": {"pct_of_capital": config.TBILL_SLEEVE_PCT,
                      "horizon": "rolling", "rule": "risk-free anchor + dry powder"},
            "core": {"symbols": core, "horizon": "long-term (buy & hold)",
                     "review": "rebalance quarterly; only BUY/HOLD names with score "
                               f">= {config.CORE_SCORE_MIN:.0f}"},
            "satellite": {"symbols": satellite, "horizon": "tactical",
                          "review": "review MONTHLY; enter only on BUY, obey the stop-loss"},
        },
        "sell_rules": [
            "Stop-loss: exit if the close breaks below the ATR trailing stop (per position).",
            "Signal exit: exit on an EXIT signal (death cross / price below the 200-MA).",
            "Trim: take partial profit on a TRIM signal (RSI > 70 or > 20% above the 50-MA).",
            "Rebalance band: trim/top-up any name that drifts > +/-5% from its target weight.",
            "Opportunity cost: rotate to T-bills if a holding's outlook falls below the "
            f"~{config.TBILL_ANNUAL_YIELD*100:.0f}% risk-free yield.",
        ],
        "cadence": {
            "monthly": "re-run the collector; apply stop-losses + signal exits on the "
                       "satellite sleeve; check rebalance bands.",
            "quarterly": "rebalance the core sleeve to target weights; re-underwrite each thesis.",
            "note": "The 2025 stamp-duty regime taxes turnover, not gains — fewer trades win.",
        },
        "expected_income_egp": {
            "tbill_annual": tbill_income,
            "net_dividends_annual": net_div_income_egp,
            "total_annual": round(tbill_income + net_div_income_egp, 2),
            "note": "Dividends are net of the 5% listed-share withholding tax.",
        },
    }


def _scene_brief() -> dict:
    """Macro brief for the dashboard header — refreshed from live research (9-Jun-2026).

    Sources (5-Jul-2026 web search): EGX30 50,533 (1-Jul close), −4.5% MoM after the
    late-Jun stamp-duty amendment selloff (weakest close 50,344 on 22-Jun), ~8% off the
    11-May ATH 54,979 but still +~54% YoY; CBE held 19% on 2-Apr and 21-May (825bp of
    2025-26 cuts paused), Goldman still models ~200bp of Q3 HIKES; headline inflation
    COOLED to 14.6% YoY (May) vs 14.9% (Apr) — lowest since Feb — but monthly CPI ran
    +1.6% and the CBE itself guides inflation accelerating through Q3-2026 (June CPI due
    ~10-Jul); EGP STRENGTHENED to ~49.1/USD (3-Jul; +5.2% MoM, 30d range 49.10–52.12);
    foreign capital returned across debt (~$4bn net buys of govt paper in one late-Jun
    week), equities and the new futures market; urea (Egypt FOB) $700–850/t on the
    Hormuz closure — a windfall for MFPC/ABUK, though Egypt is moving to link feedstock
    gas pricing to international fertilizer prices (gas ≈70% of their cost base);
    single-stock futures LIVE on COMI & TMGH, covered short selling next; petroleum-SOE
    IPO drive accelerating (ENPPI filing, MNT-Halan studying a listing); S&P DJI is
    reviewing Egypt's EM classification — liquidity-sensitive after the stamp-duty hike.
    """
    return {
        "as_of": "5 July 2026",
        "headline": ("EGX30 ~50.5k (−4.5% MoM on the stamp-duty selloff, ~8% off the "
                     "11-May ATH ~55k, still +~54% YoY and cheap ~8–9x fwd P/E) — "
                     "consolidating while the EGP firms to ~49.1 and foreign money "
                     "returns across debt, equities and futures."),
        "egp_usd": "~49.1 (3-Jul; pound +5.2% MoM — STRONGER, 30d range 49.10–52.12)",
        "inflation": "14.6% YoY (May) vs 14.9% (Apr) — lowest since Feb, but +1.6% MoM "
                     "and CBE guides acceleration through Q3; June CPI due ~10-Jul",
        "policy_rate": "19% (held 2-Apr & 21-May; 825bp of 2025-26 cuts paused, "
                       "Goldman still models ~200bp of Q3 hikes; next MPC late-Jul)",
        "tbill_12m": "~23.4% — the risk-free hurdle for any equity",
        "tailwinds": ["urea $700–850/t (Hormuz closure) — MFPC/ABUK export windfall",
                      "high-ROE banks (rate beneficiaries if hikes resume)",
                      "foreign inflows across debt (~$4bn/wk late-Jun), equities, futures",
                      "record IPO year: petroleum SOEs, ENPPI filing, MNT-Halan studying",
                      "single-stock futures live (COMI, TMGH); covered shorts next",
                      "Suez reopening optionality (Morgan Stanley's key catalyst)"],
        "risks": ["stamp-duty amendments (late-Jun) draining liquidity — S&P DJI EM "
                  "review is liquidity-sensitive",
                  "inflation re-accelerating → rate HIKES, not cuts, would re-rate cheap equities",
                  "gas feedstock repricing to intl fertilizer prices — margin risk for MFPC/ABUK",
                  "stronger EGP trims FX-earner translation gains",
                  "regional conflict (Israel/Iran/US/Houthis) → Suez & FX/energy shock"],
        "tax_note": "CGT abolished Jun-2025 → stamp duty per side (amendments approved "
                    "late-Jun-2026, rates raised); 5% WHT on dividends.",
    }


def _config_brief() -> dict:
    return {
        "gates": {"min_market_cap_egp": config.GATE_MIN_MARKET_CAP_EGP,
                  "min_avg_daily_value_egp": config.GATE_MIN_AVG_DAILY_VALUE_EGP},
        "target_bucket_weights": config.TARGET_BUCKET_WEIGHTS,
        "max_position_pct": config.MAX_POSITION_PCT,
        "max_sector_pct": config.MAX_SECTOR_PCT,
        "target_holdings": config.TARGET_HOLDINGS,
        "broker": config.ACTIVE_BROKER,
    }


def save(snapshot: dict, path: str = config.SNAPSHOT_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
    return os.path.abspath(path)


def main():
    snap = collect()
    out = save(snap)
    pf = snap["portfolio"]
    print(f"\n[agent] snapshot -> {out}")
    print(f"[agent] live data ok: {snap['live_data_ok_count']}/{snap['universe_size']} "
          f"| index ok: {snap['index_data_ok']}")
    print(f"[agent] shortlist: {', '.join(snap['shortlist'])}")
    print(f"[agent] portfolio: {pf['num_positions']} positions, "
          f"invested {pf['invested_value']} EGP, cash {pf['cash_remaining']} EGP")


if __name__ == "__main__":
    main()
