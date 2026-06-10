"""Bucket classification + composite quality scoring for EGX stocks.

Pipeline: hard eligibility gates -> bucket (first match wins) -> 0..100 quality score.
Buckets: stable_bluechip / value / growth / speculative (excluded) / watchlist.
"""

from __future__ import annotations

from app import config


def _g(m: dict, key: str, default=None):
    v = m.get(key)
    return default if v is None else v


def passes_gates(m: dict) -> tuple[bool, list[str]]:
    """Liquidity + size gates. Returns (eligible, reasons_failed)."""
    fails = []
    mc = _g(m, "market_cap")
    adv = _g(m, "avg_daily_value")
    if mc is not None and mc < config.GATE_MIN_MARKET_CAP_EGP:
        fails.append("market_cap_below_gate")
    if adv is not None and adv < config.GATE_MIN_AVG_DAILY_VALUE_EGP:
        fails.append("illiquid")
    if m.get("data_ok") is False:
        fails.append("no_live_data")
    return (len(fails) == 0, fails)


def classify(m: dict) -> str:
    beta = _g(m, "beta", 1.0)
    mc = _g(m, "market_cap", 0)
    adv = _g(m, "avg_daily_value", 0)
    pe = _g(m, "pe")
    pb = _g(m, "pb")
    dy = _g(m, "dividend_yield", 0)
    payout = _g(m, "payout_ratio", 0)
    roe = _g(m, "roe", 0)
    growth = _g(m, "eps_growth_3y", 0)
    vol = _g(m, "volatility")

    # speculative — exclude (small / illiquid / very high beta or volatility)
    if (mc < config.GATE_MIN_MARKET_CAP_EGP
            or beta > config.SPEC_MAX_BETA
            or (vol is not None and vol > config.SPEC_MAX_VOLATILITY)):
        return "speculative"

    # stable blue-chip (now partly live: realized volatility guardrail)
    if (beta < config.STABLE_MAX_BETA
            and (vol is None or vol <= config.STABLE_MAX_VOLATILITY)
            and mc >= config.STABLE_MIN_MARKET_CAP
            and (adv == 0 or adv >= config.STABLE_MIN_AVG_DAILY_VALUE)
            and dy >= config.STABLE_MIN_DIV_YIELD
            and payout <= config.STABLE_MAX_PAYOUT):
        return "stable_bluechip"

    # value
    if (pe is not None and pe < config.VALUE_MAX_PE
            and pb is not None and pb < config.VALUE_MAX_PB
            and dy >= config.VALUE_MIN_DIV_YIELD
            and roe >= config.VALUE_MIN_ROE):
        return "value"

    # growth — must reinvest, not pay nearly everything out
    if (growth >= config.GROWTH_MIN_EPS_GROWTH_3Y
            and (pe is None or pe <= config.GROWTH_MAX_PE)
            and roe >= config.GROWTH_MIN_ROE
            and payout <= config.GROWTH_MAX_PAYOUT):
        return "growth"

    return "watchlist"


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def quality_score(m: dict) -> float:
    """0..100 composite. Higher = more attractive for a balanced book."""
    w = config.SCORE_WEIGHTS

    liquidity = _norm(_g(m, "avg_daily_value", 0), 0, 100_000_000)
    vol = _g(m, "volatility")
    low_vol = 1.0 - _norm(vol, 0.20, 0.80) if vol is not None else 0.5
    # net the 5% dividend WHT — the cash an investor actually keeps
    dy = _g(m, "dividend_yield", 0) * (1.0 - config.DIV_WHT_PCT)
    payout = _g(m, "payout_ratio", 0.5)
    # reward yield but penalize unsustainable payout
    dividend = _norm(dy, 0, 0.10) * (1.0 - _norm(payout, 0.85, 1.0))
    pe = _g(m, "pe")
    valuation = 1.0 - _norm(pe, 5, 25) if pe is not None else 0.5
    roe = _norm(_g(m, "roe", 0), 0.05, 0.35)

    score = (w["liquidity"] * liquidity
             + w["low_volatility"] * low_vol
             + w["dividend"] * dividend
             + w["valuation"] * valuation
             + w["quality_roe"] * roe)
    return round(score * 100, 1)
