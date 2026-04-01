-- Market data initial schema
CREATE TABLE IF NOT EXISTS market_data.prices (
    timestamp       TIMESTAMPTZ     NOT NULL,
    instrument_id   VARCHAR(32)     NOT NULL,
    bid             NUMERIC(18,8)   NOT NULL,
    ask             NUMERIC(18,8)   NOT NULL,
    mid             NUMERIC(18,8)   NOT NULL,
    volume          NUMERIC(18,2),
    source          VARCHAR(32)     NOT NULL,
    PRIMARY KEY (timestamp, instrument_id)
);

CREATE INDEX IF NOT EXISTS ix_md_prices_instrument_time
    ON market_data.prices (instrument_id, timestamp);
