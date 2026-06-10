# Postgres as the system of record (over files / SQLite)

**Status:** accepted

For a single-user 20,000 EGP paper portfolio, a right-sized store would have been
SQLite (stdlib, file-based, fits the existing Docker data volume) or even dated
JSON files. We chose **Postgres** as a new Docker service instead, and we are
moving the previously code-defined tradable universe (`EGX_UNIVERSE`) into it as
an `instrument` master table. The driver is **future-scale ambition** — more
assets, more frequent data, richer queries, and possibly multiple portfolios —
not today's data volume.

## Considered options

- **SQLite (stdlib)** — recommended, right-sized, no new dependency or container.
  Rejected because it doesn't carry the project toward the intended scale.
- **Dated JSON files** — simplest, but gives no queryable time series; rejected.
- **Postgres** — chosen, for the scale ambition above.

## Consequences

- A third container, a DB driver, connection handling, and migrations from day one.
- `universe.py` becomes a seed script rather than the source of truth.
- `snapshot.json` is demoted to a derived read-cache, regenerated from Postgres on
  Refresh; the database is authoritative.
- This is hard to reverse once schema and history accumulate — revisit only with a
  real migration, not casually.
