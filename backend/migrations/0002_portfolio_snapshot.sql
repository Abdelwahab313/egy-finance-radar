-- ADR-0005: Portfolio Snapshot history — one dated row per as_of for the whole
-- book. Headline aggregates as structured columns (chartable without re-parsing);
-- per-lot holdings and bucket/sector weights as JSONB. Idempotent per as_of,
-- mirroring the UNIQUE(symbol, as_of) pattern used by price_history.
--
-- Aggregate columns are NULLable on purpose: rows backfilled from the git trail
-- have an exact cost_basis but no market mark for manual-NAV names (MTF, BCO),
-- and presenting a guess as measured truth would be dishonest. Such rows carry
-- reconstructed = TRUE.
CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id             BIGSERIAL PRIMARY KEY,
    as_of          DATE NOT NULL,
    reconstructed  BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = backfilled, approximate
    source         TEXT,                            -- where the row's numbers came from
    nav_total      NUMERIC(18,2),
    cost_basis     NUMERIC(18,2),
    market_value   NUMERIC(18,2),
    invested       NUMERIC(18,2),
    cash           NUMERIC(18,2),
    unrealized_pnl NUMERIC(18,2),
    unrealized_pct NUMERIC(10,6),
    deployed_pct   NUMERIC(10,6),
    holdings       JSONB NOT NULL DEFAULT '[]'::jsonb,
    bucket_weights JSONB,
    sector_weights JSONB,
    events         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (as_of)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshot_as_of ON portfolio_snapshot(as_of DESC);
