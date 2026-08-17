# ADR-0006 — Owner broker marks override vendor prices

Date: 2026-08-17
Status: Accepted

## Context

On 17-Aug-2026 the owner asked why the agent kept citing prices and news that
were stale or not about Egypt. The specific failures, all in one session:

- **ABUK.** Investing.com, TradingView, stockanalysis and african-markets all
  quoted 73.71 dated **10-Aug**. The owner's the broker screen showed **79.70**. The
  vendors were not wrong about 10-Aug — they were five sessions behind, and
  nothing in the pipeline could tell the difference between "the price" and "the
  last price a vendor happened to publish".
- **SWDY.** A web search returned the Electra Investment tender offer as if it
  were current news. It closed in **July 2024** at EGP 49.16/share against a spot
  of ~109. Only the absurdity of the number caught it.
- **16/17-Aug session data.** No English-language wrap existed at all.
- **stockanalysis.com** returned HTTP 403 to direct fetches, so even a known-good
  URL is not a reliable channel.

The root cause is not the searching. It is that the repo has exactly one price
source — `YFinanceSource` at `app/data/sources.py` — `data/snapshot.json` had not
been regenerated since 22-Jul, and there was no way to write down a number the
owner could see on their own broker screen. So the agent reached for the web,
and the web is a lagging, undated, English-biased index of this market.

## Decision

**A dated price the owner reads off the broker outranks every vendor.**

`data/marks.json` stores those numbers as `{price, as_of, source, note}` per
symbol. `MarksOverlaySource` wraps any `DataSource` and applies them after the
inner fetch. It distinguishes two failures that need different responses:

| Situation | Response |
| --- | --- |
| Mark newer than the vendor's last bar | Append it as the latest bar; report `vendor_lag_days`. This is normal for EGX. |
| Mark on the same date as a vendor bar, gap > `MARK_CONFLICT_PCT` (10%) | **Conflict.** Report it, never overwrite. Nobody agrees on the price, so the name is not orderable until reconciled against the exchange. |
| Mark older than the vendor's last bar | Ignore. The vendor caught up. |
| No vendor history at all | Unapplied. A mark cannot invent a series. |

The conflict branch is CLAUDE.md screening rule 4 ("reject any name whose vendor
quotes disagree by more than ~10% until reconciled against the EGX itself")
enforced in code rather than by eye. The whole report lands in
`snapshot.marks`, so a run that leaned on stale marks says so.

Appended bars carry `Volume = NaN`, not 0. `metrics.compute_metrics` already
drops NaN before the 60-session average-traded-value calculation, so a mark
improves the price without quietly dragging the liquidity gate down.

## Why marks, and not a second vendor

The obvious alternative was a second scraped feed so disagreements surface
automatically. Rejected: every candidate is another thing that lags, freezes or
blocks us — stockanalysis 403'd during this very investigation, and the four
vendors that *did* respond were unanimous **and unanimously wrong**, five
sessions behind. A second vendor would have agreed with the first. The broker
screen is the only EGX price the owner can always read, and on 17-Aug it beat
four vendors at once.

`MarksOverlaySource` takes a `DataSource` rather than hard-coding yfinance, so
adding EODHD later still works and gets the same overlay for free.

## Consequences

- Marks must be maintained by hand. A mark is only as good as its `as_of`, and a
  wrong date is worse than no mark. `MARK_MAX_AGE_DAYS = 7` flags stale ones in
  the snapshot rather than silently trusting them.
- `data/marks.json` is now the place to put a broker number. Saying it in chat
  does not survive the session; writing it here makes it a repo fact.
- The unverified items this does **not** fix, and must not be read as fixing:
  MTF redemption-to-usable-cash lag in T+N terms, whether Sahmy 70 (`NSF`) is on
  the broker, and what Rumble's "fundamental"/"shariah" portfolios actually are. Those
  need the app, not a feed.
- Open-ended funds (`MTF`, and `NSF`/`CMS`/`ASO` if they are ever tracked) still
  have no series to overlay. They are marked through `config.MANUAL_NAV`. A funds
  registry with its own NAV source is a separate decision, not taken here.

## Alternatives rejected

- **Fix yfinance.** The lag is in the vendor chain, not the client.
- **Scrape egx.com.eg on every run.** Authoritative, but a scraper against a
  government site is a maintenance liability and adds a failure mode to a
  pipeline that already has one. The owner can paste a mark in ten seconds.
- **Put marks in `config.MANUAL_NAV`.** That dict is untyped, undated and exists
  to mark *held* positions with no live price. Marks need a date and a source, and
  apply to names that are not held.
