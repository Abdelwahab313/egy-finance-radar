# Portfolio Snapshot history is a separate dated table, backfilled best-effort

**Status:** accepted

The book's per-stock history is already persisted (`price_history`,
`metric_snapshot`, dated `orders`, `recommendation`). The **portfolio level** —
net asset value, invested-vs-cash, unrealized P&L, bucket/sector weights, per-lot
holdings — was not: the served `snapshot.json` holds only the latest state, so
retracing how the book evolved meant reading git commits. We add a dated
**`portfolio_snapshot`** table, one idempotent row per `as_of` (mirroring the
`UNIQUE(symbol, as_of)` pattern), written during the Refresh history step.

Each row stores the headline aggregates as **structured columns** (nav_total,
cost_basis, market_value, invested, cash, unrealized_pnl, deployed_pct) plus a
**JSONB** blob for per-lot holdings and bucket/sector weights — enough to chart a
NAV/P&L curve without re-parsing, and enough detail to inspect any past frame.

Past history is **backfilled best-effort** from the git trail (reconciliation
commits with dated NAVs) plus dated `orders`/`price_history`, and every
reconstructed row is **flagged approximate**.

## Considered options

- **Whole snapshot.json blob per day** — simplest, loses nothing, but bulky and
  every chart re-parses the blob. Rejected as the primary shape.
- **Structured aggregates + JSONB holdings/weights** — chosen: compact, directly
  chartable, still detailed enough to inspect a frame.
- **Forward-only capture** — rejected: the owner explicitly wants the existing
  history remapped, and the git/DB trail makes a partial reconstruction feasible.
- **Full authoritative backfill** — rejected: manual-NAV names (MTF, BCO) that
  yfinance cannot price have only approximate historical marks; presenting them as
  exact would be dishonest.

## Consequences

- Manual-NAV holdings (MTF, BCO) never landed a `price_history` close row, so both
  the forward writer and the backfill must source their marks from `MANUAL_NAV` /
  git, not `price_history`. NAV history for these names is only as precise as those
  recorded marks.
- Reconstructed rows carry a `reconstructed`/approximate flag and must never be
  presented as measured truth; forward rows are measured at Refresh time.
- The table grows one row per Refresh day (idempotent per `as_of`), so repeated
  same-day Refreshes overwrite rather than duplicate.
