-- Create schemas for bounded contexts.
-- Per-fund schemas (fund_{slug}) are created dynamically at runtime.
CREATE SCHEMA IF NOT EXISTS security_master;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS eod;
CREATE SCHEMA IF NOT EXISTS keycloak;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Debezium CDC replication role
CREATE ROLE debezium_replication WITH REPLICATION LOGIN PASSWORD 'minihedge';
GRANT CONNECT ON DATABASE minihedge TO debezium_replication;
GRANT USAGE ON SCHEMA security_master TO debezium_replication;
GRANT SELECT ON ALL TABLES IN SCHEMA security_master TO debezium_replication;
GRANT USAGE ON SCHEMA market_data TO debezium_replication;
GRANT SELECT ON ALL TABLES IN SCHEMA market_data TO debezium_replication;
GRANT USAGE ON SCHEMA platform TO debezium_replication;
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO debezium_replication;

-- CDC publication — publish specific schemas rather than FOR ALL TABLES,
-- because TimescaleDB cannot convert a published table into a hypertable.
-- Per-fund schemas are added dynamically via ALTER PUBLICATION in fund_schema.py.
CREATE PUBLICATION minihedge_cdc FOR TABLES IN SCHEMA platform, security_master;
