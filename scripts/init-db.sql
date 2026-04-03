-- Create schemas for bounded contexts.
-- Per-fund schemas (fund_{slug}) are created dynamically at runtime.
CREATE SCHEMA IF NOT EXISTS security_master;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS keycloak;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;
