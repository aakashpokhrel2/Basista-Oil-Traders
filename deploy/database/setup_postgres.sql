-- ==============================================================================
-- PostgreSQL Production Database Initialization Script
-- Project: Basista Oil Traders Petrol Station Management System
-- Database: petrol_station_prod_db
-- User: petrol_db_user
-- ==============================================================================
-- Execute as postgres superuser:
--   sudo -u postgres psql -f deploy/database/setup_postgres.sql
-- ==============================================================================

-- 1. Create Database User (Replace with your actual secure production password)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'petrol_db_user') THEN
        CREATE ROLE petrol_db_user WITH LOGIN PASSWORD 'CHANGE_THIS_TO_STRONG_PASSWORD_123!';
    END IF;
END
$$;

-- 2. Create Production Database with UTF-8 encoding
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'petrol_station_prod_db') THEN
        CREATE DATABASE petrol_station_prod_db OWNER petrol_db_user ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template1;
    END IF;
END
$$;

-- 3. Configure Database Client Connection Settings
ALTER ROLE petrol_db_user SET client_encoding TO 'utf8';
ALTER ROLE petrol_db_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE petrol_db_user SET timezone TO 'Asia/Kathmandu';

-- 4. Grant Database Privileges
GRANT ALL PRIVILEGES ON DATABASE petrol_station_prod_db TO petrol_db_user;

-- 5. Connect to the database and set schema permissions
\c petrol_station_prod_db

GRANT ALL ON SCHEMA public TO petrol_db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO petrol_db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO petrol_db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO petrol_db_user;

-- Success confirmation notice
\echo 'PostgreSQL setup completed successfully for Basista Oil Traders!'
