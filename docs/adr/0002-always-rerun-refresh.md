# Refresh always re-runs the full recommendation pass (no same-day cache)

**Status:** accepted

Refresh is a single action that re-fetches prices/metrics AND re-runs the LLM
investigator across **every** held Position. We deliberately chose to **always
re-run** — no same-day caching, no tiered cheap/expensive split — accepting high
token cost and minutes of work per Refresh in exchange for maximum freshness. To
keep this usable, Refresh executes as a **background job** with progress, so the
dashboard never blocks.

## Considered options

- **Tiered refresh** (cheap prices/metrics frequent; LLM pass separate + cached) —
  recommended for cost control. Rejected: owner wants one button and freshest data.
- **Synchronous one-button** — rejected: would freeze the UI for minutes and risk
  HTTP timeouts.
- **Background, always re-run** — chosen.

## Consequences

- Every Refresh spends tokens proportional to the number of holdings; clicking it
  casually is expensive by design. This is intentional, not a bug to "optimize"
  with caching later without revisiting this decision.
- The investigator's existing same-day report cache is bypassed on Refresh
  (force-run); the on-demand single-ticker Investigation may still use it.
