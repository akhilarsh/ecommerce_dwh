-- ============================================================================
-- SNOWFLAKE USER PRIVILEGES FOR ECOMMERCE DWH DEPLOYMENT
-- ============================================================================
-- 
-- Replace these variables with your actual values:
-- <USER_NAME>      : The new user's name (e.g., 'ECOMMERCE_DEPLOYER')
-- <ROLE_NAME>      : Role to assign privileges to (e.g., 'ECOMMERCE_ROLE')
-- <WAREHOUSE_NAME> : Warehouse name (e.g., 'COMPUTE_WH')
-- <DATABASE_NAME>  : Database name (e.g., 'ECOMMERCE_DB')
-- <SCHEMA_NAME>    : Schema name (e.g., 'E_MART')
--
-- ============================================================================

-- ============================================================================
-- 1. CREATE ROLE (Optional - if using a dedicated role)
-- ============================================================================
CREATE ROLE IF NOT EXISTS <ROLE_NAME>;

-- ============================================================================
-- 2. WAREHOUSE PRIVILEGES
-- ============================================================================
-- Required for executing queries
GRANT USAGE ON WAREHOUSE <WAREHOUSE_NAME> TO ROLE <ROLE_NAME>;

-- ============================================================================
-- 3. DATABASE PRIVILEGES
-- ============================================================================
-- Required for USE DATABASE and accessing the database
GRANT USAGE ON DATABASE <DATABASE_NAME> TO ROLE <ROLE_NAME>;

-- ============================================================================
-- 4. SCHEMA PRIVILEGES (after schema is created)
-- ============================================================================
-- Grant all privileges on the schema
GRANT ALL PRIVILEGES ON SCHEMA <DATABASE_NAME>.<SCHEMA_NAME> TO ROLE <ROLE_NAME>;

-- OR grant specific privileges:
-- GRANT USAGE ON SCHEMA <DATABASE_NAME>.<SCHEMA_NAME> TO ROLE <ROLE_NAME>;
-- GRANT CREATE TABLE ON SCHEMA <DATABASE_NAME>.<SCHEMA_NAME> TO ROLE <ROLE_NAME>;

-- ============================================================================
-- 5. FUTURE GRANTS (for tables created in the schema)
-- ============================================================================
-- Allow operations on all future tables in the schema
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA <DATABASE_NAME>.<SCHEMA_NAME> TO ROLE <ROLE_NAME>;

-- OR grant specific privileges:
-- GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA <DATABASE_NAME>.<SCHEMA_NAME> TO ROLE <ROLE_NAME>;

-- ============================================================================
-- 6. ASSIGN ROLE TO USER
-- ============================================================================
GRANT ROLE <ROLE_NAME> TO USER <USER_NAME>;

-- Set as default role for the user
ALTER USER <USER_NAME> SET DEFAULT_ROLE = <ROLE_NAME>;
ALTER USER <USER_NAME> SET DEFAULT_WAREHOUSE = <WAREHOUSE_NAME>;


-- ============================================================================
-- EXAMPLE WITH ACTUAL VALUES:
-- ============================================================================
/*
-- Create role
CREATE ROLE IF NOT EXISTS ECOMMERCE_ROLE;

-- Warehouse access
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE ECOMMERCE_ROLE;

-- Database access
GRANT USAGE ON DATABASE ECOMMERCE_DB TO ROLE ECOMMERCE_ROLE;

-- Schema access (schema must exist beforehand)
GRANT ALL PRIVILEGES ON SCHEMA ECOMMERCE_DB.E_MART TO ROLE ECOMMERCE_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA ECOMMERCE_DB.E_MART TO ROLE ECOMMERCE_ROLE;

-- Assign to user
GRANT ROLE ECOMMERCE_ROLE TO USER ECOMMERCE_DEPLOYER;
ALTER USER ECOMMERCE_DEPLOYER SET DEFAULT_ROLE = ECOMMERCE_ROLE;
ALTER USER ECOMMERCE_DEPLOYER SET DEFAULT_WAREHOUSE = COMPUTE_WH;
*/


-- ============================================================================
-- MINIMUM REQUIRED PRIVILEGES SUMMARY:
-- ============================================================================
-- | Object    | Privilege      | Purpose                                    |
-- |-----------|----------------|--------------------------------------------|
-- | Warehouse | USAGE          | Execute queries                            |
-- | Database  | USAGE          | Access the database                        |
-- | Schema    | USAGE          | Access the schema                          |
-- | Schema    | CREATE TABLE   | Create dimension/fact/bridge tables        |
-- | Tables    | SELECT         | Validate tables via INFORMATION_SCHEMA     |
-- ============================================================================
--
-- NOTE: Database and Schema must be created beforehand by an admin.
-- This script assumes they already exist.
-- ============================================================================
