-- ADR-0007: one realised outcome per recommendation, upserted on every Refresh.
-- Stored rather than computed on read so an evaluation is dated and auditable
-- even after the vendor feed changes. correct is NULL for open/no_data rows.
CREATE TABLE IF NOT EXISTS recommendation_outcome (
    recommendation_id BIGINT PRIMARY KEY REFERENCES recommendation(id) ON DELETE CASCADE,
    symbol            TEXT NOT NULL REFERENCES instrument(symbol),
    evaluated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_days       INTEGER NOT NULL,
    window_end        DATE NOT NULL,
    entry_date        DATE,
    entry_price       NUMERIC(18,4),
    last_date         DATE,
    last_price        NUMERIC(18,4),
    max_close         NUMERIC(18,4),
    min_close         NUMERIC(18,4),
    return_pct        NUMERIC(10,6),
    status            TEXT NOT NULL CHECK (status IN ('target_hit','stop_hit','expired','open','no_data')),
    resolved_on       DATE,
    correct           BOOLEAN
);
CREATE INDEX IF NOT EXISTS idx_reco_outcome_symbol ON recommendation_outcome(symbol);
