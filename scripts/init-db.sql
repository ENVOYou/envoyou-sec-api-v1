-- Initialize ENVOYOU SEC API Database
-- PostgreSQL with TimescaleDB extension

-- Enable TimescaleDB extension for time-series data
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database user for application (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'envoyou_api') THEN
        CREATE ROLE envoyou_api WITH LOGIN PASSWORD 'secure_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT CONNECT ON DATABASE envoyou_sec TO envoyou_api;
GRANT USAGE ON SCHEMA public TO envoyou_api;
GRANT CREATE ON SCHEMA public TO envoyou_api;

-- Create initial schema comment
COMMENT ON DATABASE envoyou_sec IS 'ENVOYOU SEC API - Climate Disclosure Compliance Database';