-- Position keeping initial schema: event store + read models

-- Event store (append-only, source of truth)
CREATE TABLE IF NOT EXISTS positions.events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id    VARCHAR(128) NOT NULL,
    sequence_number BIGINT NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    event_data      JSONB NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (aggregate_id, sequence_number)
);

CREATE INDEX IF NOT EXISTS ix_pos_events_aggregate
    ON positions.events (aggregate_id, sequence_number);
CREATE INDEX IF NOT EXISTS ix_pos_events_type
    ON positions.events (event_type);

-- Read model: current positions (denormalized for fast queries)
CREATE TABLE IF NOT EXISTS positions.current_positions (
    portfolio_id    UUID NOT NULL,
    instrument_id   VARCHAR(32) NOT NULL,
    quantity        NUMERIC(18,8) NOT NULL DEFAULT 0,
    avg_cost        NUMERIC(18,8) NOT NULL DEFAULT 0,
    cost_basis      NUMERIC(18,8) NOT NULL DEFAULT 0,
    realized_pnl    NUMERIC(18,8) NOT NULL DEFAULT 0,
    market_price    NUMERIC(18,8) NOT NULL DEFAULT 0,
    market_value    NUMERIC(18,8) NOT NULL DEFAULT 0,
    unrealized_pnl  NUMERIC(18,8) NOT NULL DEFAULT 0,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, instrument_id)
);

CREATE INDEX IF NOT EXISTS ix_pos_current_portfolio
    ON positions.current_positions (portfolio_id);
