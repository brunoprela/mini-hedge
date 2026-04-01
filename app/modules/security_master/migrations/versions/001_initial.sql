-- Security master initial schema
CREATE TABLE IF NOT EXISTS security_master.instruments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    ticker          VARCHAR(32) NOT NULL UNIQUE,
    asset_class     VARCHAR(32) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    exchange        VARCHAR(32) NOT NULL,
    country         VARCHAR(2) NOT NULL,
    sector          VARCHAR(128),
    industry        VARCHAR(128),
    shares_outstanding NUMERIC(18,0),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    listed_date     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_sm_instruments_ticker ON security_master.instruments (ticker);
CREATE INDEX IF NOT EXISTS ix_sm_instruments_asset_class ON security_master.instruments (asset_class);
CREATE INDEX IF NOT EXISTS ix_sm_instruments_active ON security_master.instruments (is_active);
