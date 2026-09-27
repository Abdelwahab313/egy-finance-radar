# Recommendations are scored against realised prices in their own table

**Status:** accepted (2026-09-27)

The `recommendation` table stores a dated verdict per Position: action, price
target, stop. Nothing checked those verdicts afterwards, so the only feedback
was memory. The scorecard closes that loop: every Refresh evaluates every past
verdict against the closes that followed it and stores the result.

## Decision

- New table `recommendation_outcome`, one row per recommendation, upserted on
  every Refresh in the history step. Stored, not computed on read: the vendor
  feed drifts and sometimes freezes, so an evaluation carries its own
  `evaluated_at` and can be audited.
- **Window.** `tactical` verdicts are judged over 30 calendar days, `core` over
  365, matching the Horizon definitions in CONTEXT.md.
- **Entry price.** The first close on or after `as_of`, within 7 calendar
  days. No close in that span means `no_data`.
- **Series.** Daily closes from the `DataSource`, marks overlay included, with
  `price_history` rows as the fallback when the vendor returns nothing.
- **Status.** `target_hit` when a close reaches `price_target`, `stop_hit` when a
  close reaches `stop_loss`, whichever comes first by date. A day that touches
  both counts as `stop_hit`. No touch and the window has ended: `expired`. No
  touch and the window is still running: `open`.
- **Correct.** `add` and `hold`: `target_hit`, or `expired` with a positive
  return. `trim` and `sell`: `stop_hit`, or `expired` with a negative return.
  `open` and `no_data` rows are not scored.
- **Hit rate** is correct over scored, reported overall, by horizon and by
  action, with the count alongside so a rate on three rows reads as three rows.
- `GET /api/scorecard` returns the summary and the rows, newest first.

## Considered options

- **Compute on read.** Cheap to build, but a re-read after a feed change would
  silently change history. Rejected.
- **Score each verdict against the next verdict on the same Position.** The
  cadence is irregular and a verdict can be the last one. Rejected.
- **Use intraday highs and lows.** Stops in this project are reviewed on close,
  and broker marks are closes. Closes only.
- **Score sells by what the money did afterwards.** Would need the whole book's
  path. Out of scope; a sell is judged on the sold name alone.

## Consequences

- A sell verdict scored on the sold name says nothing about the alternative
  use of the cash. State that when reading the number.
- Fund units have no price series, so their verdicts stay `no_data`.
- The sample book ships five sample verdicts in `backend/data/recommendations.json`
  so the endpoint returns something on a clean clone. Their outcomes are
  whatever the real closes say.
- The Refresh makes one extra fetch for the symbols that carry verdicts.
