# egy-finance-radar

A personal advisor for the Egyptian Exchange (EGX). It tracks the account's
holdings and, for each one, recommends what to do next based on recent news and
stock updates, while respecting how long the owner *intends* to hold it.

## Language

**Position**:
A holding the owner currently has in one stock: its shares and cost basis,
together with its Style Bucket and its Horizon.
_Avoid_: Holding, lot.

**Order**:
A single buy or sell the owner placed at the broker. One or more Orders in the
same stock accumulate into a Position.
_Avoid_: Trade, transaction, purchase.

**Style Bucket**:
The investment *style* a stock is classified into: `stable_bluechip`, `value`,
`growth`, or `speculative`. Assigned automatically from fundamentals. Drives
target portfolio weights. Says nothing about how long the owner holds.
_Avoid_: Sleeve (when meaning style), category, class.

**Horizon**:
The owner's *intended holding period* for a Position, a deliberate choice, not
derived from the Style Bucket. Two values:
- **Core**: intended to hold long, on the order of a year; judged on whether the
  long-term thesis still holds.
- **Satellite**: intended to hold short, on the order of a month; selected on
  fundamentals (the name must be worth owning at all), timed on technicals
  (entry/exit levels, catalysts, stops); tighter sell discipline.
_Avoid_: Term, duration, hold-period. _Retired_: Tactical (renamed Satellite,
03-Sep-2026; the data and the owner's own usage had already converged on it).

**Recommendation**:
The advisor's verdict on a single Position at a point in time: an action
(hold / add / trim / sell), a rationale, and the recent news that drove it.
Differs by Horizon: a Core Position is judged on whether its long-term thesis
still holds; a Tactical Position on near-term catalysts, price target, and stop.
Recommendations are kept over time, so past verdicts can be reviewed.
_Avoid_: Signal (that's the deterministic technical indicator), advice, call.

**Investigation**:
A deep, on-demand research pass on one stock: the existing agent web-researches
recent news and writes a long-form analyst Report. A Recommendation may be
produced by an Investigation, but the two are distinct: the Report is prose for
a human; the Recommendation is a stored, structured verdict.
_Avoid_: Analysis (overloaded), research.

**Instrument**:
A stock that is part of the tracked EGX universe: its identity (ticker, name,
sector) and curated static fundamentals. Membership in the universe is what makes
a stock eligible to be classified, scored, and held. The master record of every
Instrument lives in the database.
_Avoid_: Stock (informal ok), security, ticker (that's just its symbol).

**Refresh**:
The single action that brings everything up to date: re-fetch prices and
metrics, append them to history, and re-run the recommendation pass across every
held Position. It always re-runs fully (no same-day reuse) and executes in the
background, so the dashboard stays responsive while results fill in.
_Avoid_: Sync, reload, update.

**Scene**:
The market-level Egypt-finance context a Refresh presents alongside the
Positions: the macro backdrop (index level, EGP, inflation, policy rate,
T-bill hurdle) against which every Recommendation is read. It is a dated
observation with an explicit as-of: a Scene is only as current as the day it
was captured, and is flagged stale when older than the data around it. Distinct
from the per-Instrument news an Investigation gathers: the Scene is the whole
market's weather, not one company's.
_Avoid_: Macro (informal ok), context, brief.

**Portfolio Snapshot**:
A dated record of the whole book at one point in time: its net asset value,
invested-vs-cash split, unrealized P&L, and the bucket/sector weights and
per-lot holdings that produced them. Kept as a time series so the owner can
retrace how the book evolved. Distinct from a Position (one holding) and from
the served snapshot cache (the latest state only); a Portfolio Snapshot is one
frame in the book's history.
_Avoid_: Snapshot (overloaded with the cache file), NAV point, state.
