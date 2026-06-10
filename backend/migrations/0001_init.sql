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
