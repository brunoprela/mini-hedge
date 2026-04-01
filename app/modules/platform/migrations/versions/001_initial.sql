-- Platform schema: fund registry and portfolio management

CREATE TABLE IF NOT EXISTS platform.funds (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(64) NOT NULL UNIQUE,
    name        VARCHAR(255) NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'active',
    base_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    offboarded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_platform_funds_slug ON platform.funds (slug);
CREATE INDEX IF NOT EXISTS ix_platform_funds_status ON platform.funds (status);

CREATE TABLE IF NOT EXISTS platform.portfolios (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id     UUID NOT NULL REFERENCES platform.funds(id),
    slug        VARCHAR(64) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    strategy    VARCHAR(128),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fund_id, slug)
);

CREATE INDEX IF NOT EXISTS ix_platform_portfolios_fund ON platform.portfolios (fund_id);
