# EGX Portfolio Advisor

A personal advisor for the Egyptian Exchange (EGX). It tracks the owner's real
holdings and, for each one, recommends what to do next based on recent news and
stock updates — while respecting how long the owner *intends* to hold it.

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
The investment *style* a stock is classified into — `stable_bluechip`, `value`,
`growth`, or `speculative`. Assigned automatically from fundamentals. Drives
target portfolio weights. Says nothing about how long the owner holds.
_Avoid_: Sleeve (when meaning style), category, class.

**Horizon**:
The owner's *intended holding period* for a Position — a deliberate choice, not
derived from the Style Bucket. Two values:
- **Core** — intended to hold long, on the order of a year; judged on whether the
  long-term thesis still holds.
- **Tactical** — intended to hold short, on the order of a month; judged on
  near-term news, catalysts, and price targets.
_Avoid_: Term, duration, hold-period.

**Recommendation**:
The advisor's verdict on a single Position at a point in time — an action
(hold / add / trim / sell), a rationale, and the recent news that drove it.
Differs by Horizon: a Core Position is judged on whether its long-term thesis
still holds; a Tactical Position on near-term catalysts, price target, and stop.
Recommendations are kept over time, so past verdicts can be reviewed.
_Avoid_: Signal (that's the deterministic technical indicator), advice, call.

**Investigation**:
A deep, on-demand research pass on one stock: the existing agent web-researches
recent news and writes a long-form analyst Report. A Recommendation may be
produced by an Investigation, but the two are distinct — the Report is prose for
a human; the Recommendation is a stored, structured verdict.
_Avoid_: Analysis (overloaded), research.

**Instrument**:
A stock that is part of the tracked EGX universe — its identity (ticker, name,
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
