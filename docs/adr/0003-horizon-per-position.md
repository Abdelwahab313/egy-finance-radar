# Horizon is a per-Position tag; one Position per ticker

**Status:** accepted

Each Position carries a single **Horizon** — Core (~1 year) or Tactical (~1 month)
— chosen explicitly by the owner, independent of the stock's Style Bucket. We
model **one Position per ticker**: Orders are pure dated buy/sell events, and the
Position is their running aggregate. A given ticker therefore has exactly one
Horizon.

## Consequences

- The same-ticker / split-intent case (e.g. holding some COMI as Core and buying
  more to flip Tactically) is **not supported** — it would resolve to a single
  Core position. This is a deliberate deferral, not an oversight; supporting it
  requires per-lot horizon accounting (lot selection on sells, grouped views) and
  is out of scope until it's a real need.
- Horizon is set when a Position is first opened and is editable thereafter.
- Recommendations branch on Horizon: Core is judged on long-term thesis; Tactical
  on near-term catalysts, price target, and stop.
