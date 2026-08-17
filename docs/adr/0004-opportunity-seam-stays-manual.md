# The opportunity seam stays manual: Refresh investigates holdings, not the shortlist

**Status:** accepted

The system has two arms: the deterministic engine, which ranks the whole universe
and surfaces a **shortlist** of opportunities, and the **Investigator**, which
deep-researches ONE ticker into a Report + stored Recommendation. A Refresh runs
the Investigator over **every held Position** but deliberately **not** over the
shortlisted names the owner does not yet hold. Deep-researching a new opportunity
is a manual, on-demand act (one `POST /api/investigate` per name).

The two arms are therefore intentionally **decoupled**, not a single automatic
pipeline. The engine tells you *what to look at*; you decide *what to investigate*.

## Considered options

- **Auto-investigate top-N shortlist on every Refresh** — closes the loop so
  opportunities get the same deep research as holdings. Rejected: multiplies the
  already-expensive Refresh token cost (ADR-0002) across names the owner may never
  buy, and the shortlist churns.
- **One-click "investigate all shortlist" trigger**, separate from Refresh —
  rejected for now: adds a surface with no demonstrated need; the owner already
  investigates the one or two names they care about.
- **Manual, per-name investigation** — chosen.

## Consequences

- The owner eyeballs the shortlist, then investigates deliberately. This is a
  feature, not a missing wire — do not "finish the pipeline" by auto-investigating
  the shortlist without revisiting this decision and its cost implications.
- There is no stored Recommendation for a name until it is either held or manually
  investigated. Opportunity coverage depends on the owner pulling, not the system
  pushing.
- Because the engine's ranking and the Investigator's verdict are produced
  independently, they can disagree. That contradiction is surfaced as a soft flag
  (signal/reco conflict), not resolved automatically — the owner keeps the call.

## Amendment — 04 Aug 2026: a named watchlist is investigated every Refresh

The decision above holds for the shortlist, which churns. It does **not** hold for
a small set of names the owner has already decided to track to a buy or a
rejection. Those were being re-researched by hand every review cycle — the manual
pull the ADR assumed turned out to be the bottleneck, not the safeguard.

``config.INVESTIGATE_WATCHLIST`` is now investigated on every Refresh alongside
held Positions. The rejected option was "auto-investigate top-N shortlist"; this is
not that. The distinguishing constraints:

- The list is **explicit and named**, never derived from the ranking, so it cannot
  churn with the engine's output.
- It is **bounded and short** — each entry is one full LLM investigation per
  Refresh, so length is a direct cost multiplier (the ADR-0002 concern is
  unchanged, just accepted for a handful of names).
- Entries are **temporary by construction**: a name leaves the list when it is
  bought (it becomes a Position and is covered anyway) or rejected.
- Watchlist names are not held, so they have no Position horizon. ``investigate``
  falls back to the sidecar's horizon, then ``'tactical'`` — meaning a watchlist
  Recommendation is judged on near-term catalysts, which is the correct framing for
  a name being sized for entry.

The seam itself stays manual for everything else: `POST /api/investigate` remains
the way to research a name that is neither held nor on the list.
