-- One-time account setup. Run as ACCOUNTADMIN (or a role that can create roles/warehouses).
-- Needs the Snowflake semantic view feature (sv_hed_at_risk_students is a SEMANTIC VIEW).
USE ROLE ACCOUNTADMIN;
CREATE WAREHOUSE IF NOT EXISTS WORKSHOP_WH WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
CREATE ROLE IF NOT EXISTS WORKSHOP_TRANSFORMER;
GRANT USAGE, OPERATE ON WAREHOUSE WORKSHOP_WH TO ROLE WORKSHOP_TRANSFORMER;
-- dbt creates the target + sv_higher_education schemas, so it needs database-level create rights.
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_SUMMIT_2026_HOL_DB;
GRANT ALL ON DATABASE SNOWFLAKE_SUMMIT_2026_HOL_DB TO ROLE WORKSHOP_TRANSFORMER;
-- Grant the role to yourself / attendees:
-- GRANT ROLE WORKSHOP_TRANSFORMER TO USER <your_user>;
