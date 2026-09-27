"""Central configuration: capital, eligibility gates, bucket thresholds, portfolio
targets, and the trading-cost model. Tuned to June-2026 EGX levels — adjust here."""

from __future__ import annotations

import os

# --- Database ----------------------------------------------------------------
# Postgres is the system of record (ADR-0001). Inside compose the backend gets
# DATABASE_URL=postgresql://egx:egx@db:5432/egx; the host venv defaults to the
# 5433:5432 port mapping on the db service for local runs / verification.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://egx:egx@localhost:5433/egx")

# --- Account -----------------------------------------------------------------
STARTING_CAPITAL_EGP: float = 200_000.00  # sample book; cash = capital minus cost basis of data/orders.json lots

# Manual NAV override for fund units yfinance cannot price. A stale entry here
# silently freezes whatever share of the book those units represent.
MANUAL_NAV: dict[str, float] = {
    # Sample NAVs. Derive a real mark from the broker's Market Value column,
    # (cost +/- unrealized) / units, not from a 2dp displayed price.
    "MTF":  215.10,   # Misr Insurance Takaful (short-term fixed income)
    "CI30":  38.50,   # Misr Equity Fund (EGX30 Capped)
    "CMS":   22.40,   # Misr Sharia Equity Fund (EGX33 Shariah)
    "BMM":    2.60,   # Beltone Meya Meya (EGX100 EWI)
    "BRE":    2.10,   # Beltone Real Estate (sector fund)
}

# --- Owner price marks (ADR-0006) --------------------------------------------
# data/marks.json holds dated prices the owner read off the broker or the
# exchange. MarksOverlaySource applies them over whatever the vendor returned:
# a newer mark becomes the latest bar, a same-date mark that disagrees by more
# than MARK_CONFLICT_PCT is a screening-rule-4 conflict and blocks the name.
MARKS_PATH = "data/marks.json"
MARK_CONFLICT_PCT: float = 0.10        # CLAUDE.md rule 4: >~10% vendor disagreement
MARK_MAX_AGE_DAYS: int = 7             # older marks still apply, but are flagged stale

# Symbols the Refresh recommendation pass investigates on EVERY run even though
# they are not held. ADR-0004 keeps the opportunity seam manual by default (the
# Refresh investigates held Positions only); this is the owner's explicit,
# named-and-bounded exception — see the ADR amendment.
# Each entry adds one full LLM investigation per Refresh, so keep the list short
# and drop a name once it is bought (it becomes a Position) or rejected.
INVESTIGATE_WATCHLIST: tuple[str, ...] = (
    "ABUK",    # H1 2026 net profit +119% YoY; gas supply confirmed stable. Yield is
               # ~2.9% trailing, NOT the 8.4% carried here until 17-Aug-2026: the
               # 6.00 DPS was coupon 47 (FY to Jun-2025), fully paid by 26-Feb-2026.
               # Dec-2025 transition coupon was 2.30 (ex 20-Apr-2026, both legs paid).
               # Next declaration ~Mar-2027 AGM — no dividend catalyst before then.
    "TMGH",    # EMFD replacement in real estate; liquid (3.35m sh 03-Aug)
    "HRHO",    # Q2 2026 PUBLISHED 13-Aug-2026 (not 19-Aug as previously recorded):
               # net profit EGP 776m, -3% YoY, on revenue EGP 6.5bn +7%. Catalyst spent.
    # EAST dropped 03-Sep-2026: the vendor conflict it was listed for is resolved —
    # into a REJECT (P/E 11.56 not 6.5, H1 earnings -4.2%, payout > EPS; see
    # reports/EAST_20260903.md and the universe.py entry).
    "VLMR",    # only USD-quoted EGX line (ex-EKHO); BLOCKED — unpriceable + broker unconfirmed
    "SWDY",    # FX-earning industrial, but thin (371k sh 03-Aug vs COMI 4.12m)
    # PHAR deliberately excluded 04-Aug-2026: limit-up +20% on BOTH 02- and 03-Aug
    # (+55% in four sessions) on an EDA pricing formula still only "under study",
    # decision expected sometime in Aug-2026. Unfillable up, unexitable down.
    # Re-add only once the EDA actually announces a formula.
)

# --- Yahoo Finance symbols ---------------------------------------------------
YF_SUFFIX = ".CA"                       # EGX on Yahoo (Cairo & Alexandria)
EGX30_INDEX = "^CASE30"                 # EGX30 index symbol on Yahoo
USDEGP = "EGPUSD=X"                      # for optional USD-denominated views

# --- Eligibility gates (must pass ALL or the stock is dropped) ---------------
GATE_MIN_MARKET_CAP_EGP = 5_000_000_000     # >= 5bn EGP
GATE_MIN_AVG_DAILY_VALUE_EGP = 3_000_000    # >= 3m EGP traded/day (liquidity)

# --- Bucket thresholds -------------------------------------------------------
# stable blue-chip
STABLE_MAX_BETA = 1.0
STABLE_MAX_VOLATILITY = 0.55             # annualized; live guardrail on "stable"
STABLE_MIN_MARKET_CAP = 50_000_000_000
STABLE_MIN_AVG_DAILY_VALUE = 20_000_000
STABLE_MIN_DIV_YIELD = 0.03
STABLE_MAX_PAYOUT = 0.85
# value
VALUE_MAX_PE = 9.0
VALUE_MAX_PB = 1.8                        # loosened from 1.6 to admit cheap, high-ROE
                                          # names (e.g. EGAL pb ~1.78). NOTE: the 5%
                                          # dividend gate below still blocks EGAL (4%).
VALUE_MIN_DIV_YIELD = 0.05
VALUE_MIN_ROE = 0.15
# growth
GROWTH_MIN_EPS_GROWTH_3Y = 0.15
GROWTH_MAX_PE = 25.0
GROWTH_MIN_ROE = 0.12
GROWTH_MAX_PAYOUT = 0.60                  # real growth firms reinvest; a ~all-out
                                          # payout (e.g. EAST ~99%) is a dividend
                                          # name, not growth — keep it out of growth
# speculative (excluded)
SPEC_MAX_BETA = 1.6
SPEC_MAX_VOLATILITY = 0.80                # above this annualized vol -> speculative

# --- Composite quality score weights (sum to 1.0) ----------------------------
SCORE_WEIGHTS = {
    "liquidity": 0.25,
    "low_volatility": 0.20,
    "dividend": 0.20,
    "valuation": 0.20,
    "quality_roe": 0.15,
}

# --- Shortlist + portfolio construction --------------------------------------
SHORTLIST_SIZE = 12
BUCKET_CAPS = {                          # max names presented per bucket
    "stable_bluechip": 3,
    "value": 3,
    "growth": 3,
    "speculative": 0,
}
TARGET_BUCKET_WEIGHTS = {                # balanced value+growth tilt
    "stable_bluechip": 0.40,
    "value": 0.35,
    "growth": 0.25,
}
MAX_POSITION_PCT = 0.25                  # no single name > 25% of invested
MAX_SECTOR_PCT = 0.40                    # no single sector-GROUP > 40% of invested
TARGET_HOLDINGS = 5                      # realistic for a small account (4-6)

# Concentration caps treat these labels as ONE economic bet (a bank, an
# investment bank and a broker are all the same rate/credit cycle). Without this,
# a bank, an investment bank and a fintech can sail past the sector cap as three
# "different" sectors while really being one financials bet.
SECTOR_GROUPS = {
    "Banking": "Financials",
    "Financial Services": "Financials",
    "Fintech": "Financials",
}

# --- Signal gate -------------------------------------------------------------
# Never BUILD a position in a name the technical engine is telling you to leave.
# The classifier/score path and the signal path used to be disconnected, so a
# build could fund a name the signal engine simultaneously flagged EXIT.
BLOCK_SIGNALS = {"EXIT", "AVOID"}

# --- Core / satellite split + cash management --------------------------------
# A name is "core" (long-term, rebalance quarterly) if it scores well AND the
# trend is healthy; everything else that passes the gate is "satellite"
# (tactical, review monthly, tighter sell discipline).
CORE_SCORE_MIN = 70.0
CORE_SIGNALS = {"BUY", "HOLD"}

# Explicit risk-free sleeve. With 12-month EGP T-bills ~23% (Jun-2026) cash is a
# real competing asset, not a leftover — carve it out deliberately, not as a buffer.
TBILL_SLEEVE_PCT = 0.15                   # share of capital parked in T-bills
                                          # (0.15 -> ~80% deployable after the cash buffer)
CASH_BUFFER_PCT = 0.05                    # uninvested cash buffer carved off the top
                                          # by build_portfolio(); was referenced by
                                          # account.py but missing here (collector crash)
TBILL_ANNUAL_YIELD = 0.234               # ~12-month EGP T-bill gross yield, Jun-2026
DIV_WHT_PCT = 0.05                        # 5% withholding tax on listed dividends (residents)

# --- Trading-cost model (per side, EGP) --------------------------------------
# CGT abolished Jun-2025; replaced by a stamp duty. Plus EGX + MCDR fees.
# Default broker = low-cost digital (low-cost digital). Switch BROKER for a comparison.
STAMP_DUTY_PCT = 0.00125                 # ~0.125% per side
EGX_FEE_PCT = 0.00012
MCDR_FEE_PCT = 0.000125
BROKER = {
    "digital": {"pct": 0.001, "min_egp": 2.0},     # ~0.1% + EGP 2 min
    "traditional": {"pct": 0.005, "min_egp": 15.0},  # 0.5% + EGP 15 min
}
ACTIVE_BROKER = "digital"

# --- Technical / momentum signal engine --------------------------------------
SMA_FAST = 50
SMA_SLOW = 200
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ATR_PERIOD = 14
ATR_STOP_MULT = 2.5                 # trailing stop = price - mult*ATR
CROSS_LOOKBACK = 5                  # bars to detect a recent MA crossover
BREAKOUT_NEAR_HIGH_PCT = 0.03       # within 3% of 52w high = breakout zone
PULLBACK_NEAR_FAST_PCT = 0.04       # within 4% of the 50-MA = healthy pullback
EXTENDED_ABOVE_FAST_PCT = 0.20      # >20% above 50-MA = extended -> trim
REWARD_RISK = 2.0                   # take-profit at 2x the stop distance

# --- Cache -------------------------------------------------------------------
SNAPSHOT_PATH = "data/snapshot.json"
HISTORY_LOOKBACK = "2y"                  # price history window for metrics

# --- Stock investigation agent (headless Claude Code) ------------------------
# `investigate()` precomputes deterministic numbers, then spawns `claude -p`
# driving the `stock-investigator` subagent to web-research + write the report.
ORDERS_PATH = "data/orders.json"         # user-placed lots, marked to live prices
REPORTS_DIR = "data/reports"             # one SYMBOL_DATE.md per investigation
CLAUDE_BIN = "claude"                    # headless Claude Code CLI (reuses login)
INVESTIGATE_MODEL = "sonnet"
INVESTIGATE_MAX_TURNS = 20
INVESTIGATE_TIMEOUT_S = 600              # kill the headless run after 10 min
                                         # (web research + report write is slow)
