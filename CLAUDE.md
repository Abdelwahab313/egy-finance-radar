# egy-finance-radar: working rules

EGX research tool for one retail account: a low-risk core (money-market fund
plus cash) and a small satellite sleeve of single names. Output is one short
plan with concrete orders, never an essay. Domain vocabulary: `CONTEXT.md`.
Decisions: `docs/adr/`. Nothing here is investment advice.

## State

- Postgres is the store (ADR-0001). `backend/data/orders.json` seeds lots,
  `backend/data/marks.json` holds dated broker marks that override vendor
  prices (ADR-0006), `backend/data/portfolio_history.json` holds snapshot
  frames (ADR-0005, a dict with a `rows` array). `snapshot.json` is a cache.
- The tracked data files are a fictional sample book on real EGX tickers.
- `config.py` thresholds are parameters of the pipeline, not rules of thumb.

## Screening gates, in order

1. Liquidity vs ticket and vs exit. A thin name means smaller size.
2. No entry after a limit-up in either of the prior two sessions.
3. Unexplained volume: stand aside until a disclosure explains it or volume
   holds under about 2x norm for five sessions.
4. Vendor quotes more than 10% apart: no price conclusion until reconciled.
5. Verify the ticker is current (renames, splits). Zero volume in one vendor
   can be a dead feed, not a dead symbol. Confirm on a second source.
6. Sizing: min 2% of NAV, max 8% per new position. Name the funding source.
7. Market cap >= 5bn EGP, ADTV >= 3m EGP/day, growth P/E <= 25, value P/E <= 9
   with yield >= 5%. Extension above the 50-day is advisory, never a reject.

## Data traps

- yfinance `fast_info` is wrong on EGX. Use `.history()` and check that OHLC
  is not identical across sessions (frozen feed).
- Derive fund marks from the broker's Market Value column, not the 2dp price.
- Date every price and name its source. "Not found" is a valid finding.
- Arabic sources first for disclosures; English lags days.

## Plans

Session plans are at most 80 lines: book table, orders with dated
cancel-if-unfilled, position after fills, open decisions. Cut analysis before
cutting the order table.
