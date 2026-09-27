# Implementation Plan: Postgres-backed egy-finance-radar

This is the **shared contract** for a 6-step build. Every step is executed by a
separate subagent; they all read this file so table names, the driver, and the
holdings/recommendation contracts never drift. Read it alongside `CONTEXT.md`
(domain language) and `docs/adr/0001..0003` (decisions). Honour the language in
CONTEXT.md (Position, Order, Horizon, Recommendation, Instrument, Refresh).

## Ground rules

- **Minimal diff.** Reuse what exists. Don't add abstraction layers, config
  providers, or "future flexibility" beyond what a step needs.
- **Don't break the running app.** The Docker stack (frontend :5040, backend
  :8000 internal) is live. Each step must leave the app runnable.
- Python lives in `backend/`, venv at `backend/.venv` (already has `peewee==4.0.6`,
  `python-dotenv`). Run python as `backend/.venv/bin/python -m app...` with
  `cwd=backend`.

## Tech decisions (fixed — do not relitigate)

- **DB:** Postgres 16, new `db` service in `docker-compose.yml`.
- **Driver/ORM:** **peewee** (already installed) on **psycopg2-binary** (add to
  `requirements.txt`, `>=2.9.10` for py3.13). Use `peewee.PostgresqlDatabase`.
  If peewee+psycopg has a py3.13 wheel issue, verify with the find-docs skill
  before switching anything — psycopg2-binary is the expected path.
- **Connection:** read `DATABASE_URL` from env. Add to `config.py`:
  `DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://egx:egx@localhost:5433/egx")`.
  Inside compose the backend gets `DATABASE_URL=postgresql://egx:egx@db:5432/egx`.
  Host port `5433:5432` is mapped on `db` so the venv can connect from the host
  for local runs/verification.
- **Migrations:** numbered SQL files in `backend/migrations/NNNN_*.sql`, applied by
  a tiny runner `python -m app.db.migrate` that tracks applied versions in a
  `schema_migrations(version TEXT PK, applied_at TIMESTAMPTZ DEFAULT now())` table
  and applies each unapplied file in order, each in its own transaction.
- **DB package layout:**
  - `app/db/__init__.py` — exposes the configured peewee `db` object + `connect()`/`close()` helpers.
  - `app/db/models.py` — peewee models mapping the tables below (models are for
    queries; the SQL migration is the authoritative DDL — keep them in sync).
  - `app/db/migrate.py` — migration runner (CLI).
  - `app/db/seed.py` — idempotent seeder (step 2).

## Canonical schema (authoritative DDL — `0001_init.sql`)

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS instrument (
    symbol       TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    sector       TEXT NOT NULL,
    fundamentals JSONB NOT NULL DEFAULT '{}'::jsonb,
    in_universe  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One Position per ticker (ADR-0003). Horizon is owner intent, NOT the bucket.
CREATE TABLE IF NOT EXISTS position (
    symbol     TEXT PRIMARY KEY REFERENCES instrument(symbol),
    horizon    TEXT NOT NULL CHECK (horizon IN ('core','tactical')),
    opened_at  DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pure dated buy/sell events; a Position is their running aggregate.
CREATE TABLE IF NOT EXISTS orders (
    id         BIGSERIAL PRIMARY KEY,
    symbol     TEXT NOT NULL REFERENCES instrument(symbol),
    side       TEXT NOT NULL DEFAULT 'buy' CHECK (side IN ('buy','sell')),
    shares     NUMERIC(18,4) NOT NULL CHECK (shares > 0),
    price      NUMERIC(18,4) NOT NULL CHECK (price > 0),   -- exec price, EGP
    traded_at  DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);

CREATE TABLE IF NOT EXISTS price_history (
    id         BIGSERIAL PRIMARY KEY,
    symbol     TEXT NOT NULL REFERENCES instrument(symbol),
    as_of      DATE NOT NULL,
    close      NUMERIC(18,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, as_of)
);

CREATE TABLE IF NOT EXISTS metric_snapshot (
    id         BIGSERIAL PRIMARY KEY,
    symbol     TEXT NOT NULL REFERENCES instrument(symbol),
    as_of      DATE NOT NULL,
    bucket     TEXT,
    score      NUMERIC(8,2),
    metrics    JSONB NOT NULL DEFAULT '{}'::jsonb,
    signal     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, as_of)
);

CREATE TABLE IF NOT EXISTS news (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT NOT NULL REFERENCES instrument(symbol),
    headline     TEXT NOT NULL,
    url          TEXT,
    source       TEXT,
    published_at DATE,
    summary      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_symbol ON news(symbol);

-- The advisor's stored, structured verdict on a Position at a point in time.
CREATE TABLE IF NOT EXISTS recommendation (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT NOT NULL REFERENCES instrument(symbol),
    as_of        DATE NOT NULL,
    horizon      TEXT NOT NULL CHECK (horizon IN ('core','tactical')),
    action       TEXT NOT NULL CHECK (action IN ('hold','add','trim','sell')),
    rationale    TEXT,
    price_target NUMERIC(18,4),
    stop_loss    NUMERIC(18,4),
    news_ids     JSONB,        -- array of news.id rows that drove it
    report_file  TEXT,         -- filename of the prose Report, if any
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reco_symbol ON recommendation(symbol);
```

## Stable contracts other steps depend on

- **Horizon values** are the lowercase strings `'core'` / `'tactical'` everywhere
  (DB, JSON, API). The frontend may display "Core"/"Tactical".
- **Holdings block** (`collector._holdings_block`) keeps its current JSON shape and
  field names exactly (frontend `Holdings`/`HoldingLot` types depend on it). Step 3
  only changes its *data source* (DB orders, not orders.json). It MAY add a
  per-lot/position `horizon` field; it must not rename or drop existing fields.
- **Snapshot cache** (`snapshot.json`) stays a write target of `save()`; it is now
  derived. Don't change top-level keys the frontend reads (`stocks`, `portfolio`,
  `holdings`, `scene`, `shortlist`, `starting_capital_egp`, ...).
- **Recommendation API** (added in step 4/5): `GET /api/recommendations?symbol=SYM`
  returns rows newest-first as
  `{symbol, as_of, horizon, action, rationale, price_target, stop_loss, report_file}`.
- **Seed horizons:** `SEED_HORIZONS` in `db/seed.py`; sample book has four core
  lines and two tactical. Several lots in one symbol collapse into one Position.

## Deployment note — the LLM recommendation pass is a host-run job

The headless `claude` CLI (used by the investigator and by Refresh's recommendation
pass) is logged in on the **host**, not installed in the backend container. So:

- **In the container**, Refresh runs the deterministic half only (collect + snapshot
  cache + `price_history`/`metric_snapshot` upserts). The recommendation pass detects
  `claude` is absent and skips cleanly (phase: `recommendations: skipped (claude
  unavailable …)`) rather than failing per-symbol. Seed runs on container startup.
- **On the host**, run the full pass (it reaches Postgres via the `localhost:5433`
  mapping and uses the host's logged-in Claude):

  ```sh
  cd backend && DATABASE_URL=postgresql://egx:egx@localhost:5433/egx \
    .venv/bin/python -m app.agent.refresh            # full pass incl. recommendations
    # add --no-recommendations for the deterministic-only refresh
  ```

This keeps the deployment simple — no Claude Code or credentials baked into the image.

## Verification expectation per step

Each step must actually run against a live Postgres, not just typecheck:
`docker compose up -d db` (waits healthy), then run the relevant
`backend/.venv/bin/python -m app...` command from `cwd=backend` with
`DATABASE_URL=postgresql://egx:egx@localhost:5433/egx`, and show the resulting
rows / output. Run the existing test suite (`backend/.venv/bin/python -m pytest`)
and report pass/fail. Leave the stack runnable.

## Step ledger (update as you go)

- [x] 1 — Postgres service + driver + schema/migrations
- [x] 2 — Seed instruments/orders/positions
- [x] 3 — Repoint reads/writes to Postgres
- [x] 4 — Investigator: horizon-aware + structured recommendation/news rows
- [x] 5 — Refresh: background recommendation pass
- [x] 6 — Dashboard: order-form fields + recommendations/history
