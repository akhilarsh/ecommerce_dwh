-- ============================================================================
-- POSTGRESQL ROLE + USER + DATABASE + SCHEMA GRANTS FOR ECOMMERCE DWH
-- ============================================================================
--
-- Database  : ecommerce_db
-- Schema    : e_mart            (DWH tables — Phase 10 deployment target)
-- Role      : ecommerce_role    (NOLOGIN group role; collects all privileges)
-- User      : ecommerce_user    (LOGIN role; member of ecommerce_role)
--
-- Naming mirrors Redshift (ecommerce_role / ecommerce_user), Databricks and
-- Snowflake conventions so cross-platform docs / scripts stay consistent.
-- These object names must match POSTGRES_DATABASE / POSTGRES_SCHEMA /
-- POSTGRES_USER in your .env.
--
-- Two parts, run in different database connections:
--   PART A. Cluster-level objects   (role, user, database)
--           -> run while connected to the `postgres` maintenance database.
--   PART B. Database-level grants    (schema, table privileges, defaults)
--           -> run while connected to `ecommerce_db` (\c ecommerce_db).
--
-- Both parts must be run by a SUPERUSER (or a role with CREATEROLE +
-- CREATEDB). Unlike `setup-tables`, PostgreSQL cannot CREATE DATABASE from
-- inside the target connection, and role/database creation is cluster-scoped,
-- so an admin must run PART A up front.
--
-- Run order:
--   1. Admin, connected to `postgres`, runs PART A  (role, user, database).
--   2. Admin reconnects to `ecommerce_db` (\c) and runs PART B  (schema + grants).
--   3. Anyone verifies                                          (PART B.7).
--
-- Idempotency: every statement is safe to re-run. Role/database creation is
-- guarded (roles via DO blocks, database via the \gexec pattern), and all
-- GRANT / CREATE SCHEMA IF NOT EXISTS statements are naturally idempotent.
-- ============================================================================


-- ============================================================================
-- PART A. CLUSTER-LEVEL OBJECTS  (connect to the `postgres` database first)
-- ============================================================================
-- e.g.  psql -h localhost -U postgres -d postgres -f sql/postgres/03_user_grants.sql
-- (or paste PART A while connected to any maintenance DB, then \c ecommerce_db
--  and paste PART B).

-- ----------------------------------------------------------------------------
-- A.1. CREATE THE GROUP ROLE  (NOLOGIN — collects privileges only)
-- ----------------------------------------------------------------------------
-- PostgreSQL has no `CREATE ROLE IF NOT EXISTS`, so guard with a DO block.
-- A group role has no password and cannot log in; it exists purely to be
-- granted to one or more login users.
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ecommerce_role') THEN
        CREATE ROLE ecommerce_role NOLOGIN;
    END IF;
END
$$;


-- ----------------------------------------------------------------------------
-- A.2. CREATE THE DEPLOYMENT USER  (LOGIN role with a password)
-- ----------------------------------------------------------------------------
-- The DB user name must match POSTGRES_USER in your .env.
--
-- SECURITY: never commit a real password here. Replace the placeholder below
-- with a strong secret at run time and keep the value only in .env (gitignored),
-- .pgpass, or a secret manager. Example using psql variable substitution:
--
--   psql -v pg_user_password="'$POSTGRES_PASSWORD'" -f 03_user_grants.sql
--
-- CREATEDB is optional and only useful if you want this user (rather than an
-- admin) to be able to create other databases.
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ecommerce_user') THEN
        CREATE ROLE ecommerce_user LOGIN PASSWORD '__SET_A_STRONG_PASSWORD__';
    END IF;
END
$$;


-- ----------------------------------------------------------------------------
-- A.3. ASSIGN THE GROUP ROLE TO THE USER  (membership)
-- ----------------------------------------------------------------------------
-- INHERIT (the default) means ecommerce_user automatically uses privileges
-- granted to ecommerce_role without needing SET ROLE.
GRANT ecommerce_role TO ecommerce_user;


-- ----------------------------------------------------------------------------
-- A.4. CREATE THE DATABASE  (owned by ecommerce_user)
-- ----------------------------------------------------------------------------
-- PostgreSQL supports neither `CREATE DATABASE IF NOT EXISTS` nor running
-- CREATE DATABASE inside a transaction/DO block, so use the psql \gexec
-- pattern: the SELECT emits a CREATE DATABASE command only when the database
-- is absent, and \gexec runs whatever the query returned.
--
-- Owner = ecommerce_user so the user can fully manage its own database.
SELECT 'CREATE DATABASE ecommerce_db OWNER ecommerce_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'ecommerce_db')\gexec


-- ----------------------------------------------------------------------------
-- A.5. DATABASE-LEVEL PRIVILEGES  (ON ROLE)
-- ----------------------------------------------------------------------------
-- CONNECT   : allow opening a connection to the database.
-- CREATE    : allow creating new schemas in the database.
-- TEMPORARY : allow creating temp tables (some query paths need them).
-- NOTE: PostgreSQL database privileges are CONNECT / CREATE / TEMPORARY —
-- there is no USAGE ON DATABASE (that's a Redshift-ism / schema-level concept).
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE ecommerce_db TO ecommerce_role;


-- ============================================================================
-- >>> RECONNECT NOW:  \c ecommerce_db  <<<
-- ============================================================================
-- Everything below is DATABASE-SCOPED (schemas, schema/table grants, and
-- ALTER DEFAULT PRIVILEGES all live inside a single database). Running PART B
-- while still connected to `postgres` would create the schema and defaults in
-- the wrong database.
\c ecommerce_db


-- ============================================================================
-- PART B. DATABASE-LEVEL GRANTS  (connected to ecommerce_db)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- B.1. CREATE THE SCHEMA  (skip if `dwh setup-tables` will create it)
-- ----------------------------------------------------------------------------
-- Owned by ecommerce_user so the role can fully manage it (CREATE / DROP /
-- ALTER TABLE all require ownership or membership in the owning role).
CREATE SCHEMA IF NOT EXISTS e_mart AUTHORIZATION ecommerce_user;


-- ----------------------------------------------------------------------------
-- B.2. SCHEMA-LEVEL PRIVILEGES  (ON ROLE)
-- ----------------------------------------------------------------------------
-- Redundant with AUTHORIZATION ecommerce_user above (the user owns the schema,
-- and the role gets it transitively), but explicit is clearer and handles the
-- case where the schema was created earlier by a different user.
-- USAGE  : look up / reference objects in the schema.
-- CREATE : create new objects (tables, sequences, views) in the schema.
GRANT USAGE, CREATE ON SCHEMA e_mart TO ecommerce_role;


-- ----------------------------------------------------------------------------
-- B.3. TABLE-LEVEL PRIVILEGES ON EXISTING TABLES  (ON ROLE)
-- ----------------------------------------------------------------------------
-- Applies to tables that already exist at the time this script runs. If the
-- schema is empty (fresh setup), this is a no-op — B.5 handles future tables.
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
ON ALL TABLES IN SCHEMA e_mart TO ecommerce_role;


-- ----------------------------------------------------------------------------
-- B.4. SEQUENCE PRIVILEGES ON EXISTING SEQUENCES  (ON ROLE)
-- ----------------------------------------------------------------------------
-- Surrogate keys backed by SERIAL / GENERATED ... AS IDENTITY use sequences.
-- USAGE + SELECT let the role read/advance them via nextval()/currval().
GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA e_mart TO ecommerce_role;


-- ----------------------------------------------------------------------------
-- B.5. DEFAULT PRIVILEGES FOR FUTURE OBJECTS  (ON ROLE)
-- ----------------------------------------------------------------------------
-- ALTER DEFAULT PRIVILEGES makes objects created LATER inherit these grants
-- automatically, so this script never has to be re-run after `setup-tables`.
--
-- `FOR ROLE ecommerce_user` is REQUIRED: default privileges only apply to
-- objects created by the named role. Since `dwh setup-tables` connects as
-- ecommerce_user, defaults must be scoped to that role — not to the superuser
-- running this script. (FOR ROLE and FOR USER are synonyms in PostgreSQL.)
ALTER DEFAULT PRIVILEGES FOR ROLE ecommerce_user IN SCHEMA e_mart
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLES TO ecommerce_role;

ALTER DEFAULT PRIVILEGES FOR ROLE ecommerce_user IN SCHEMA e_mart
    GRANT USAGE, SELECT ON SEQUENCES TO ecommerce_role;


-- ----------------------------------------------------------------------------
-- B.6. (OPTIONAL) MAKE e_mart THE USER'S DEFAULT SEARCH_PATH
-- ----------------------------------------------------------------------------
-- So unqualified table names resolve to e_mart for ecommerce_user without
-- prefixing every query with the schema. Comment out if you prefer explicit
-- schema qualification everywhere.
ALTER ROLE ecommerce_user IN DATABASE ecommerce_db SET search_path = e_mart, public;


-- ----------------------------------------------------------------------------
-- B.7. VERIFY GRANTS
-- ----------------------------------------------------------------------------
-- Role membership (is ecommerce_user a member of ecommerce_role?):
SELECT r.rolname       AS member,
       g.rolname       AS granted_role
FROM   pg_auth_members m
JOIN   pg_roles r ON r.oid = m.member
JOIN   pg_roles g ON g.oid = m.roleid
WHERE  g.rolname = 'ecommerce_role';

-- Database-level privileges held by the role:
SELECT 'ecommerce_db' AS database_name,
       has_database_privilege('ecommerce_role', 'ecommerce_db', 'CONNECT')   AS can_connect,
       has_database_privilege('ecommerce_role', 'ecommerce_db', 'CREATE')    AS can_create,
       has_database_privilege('ecommerce_role', 'ecommerce_db', 'TEMPORARY') AS can_temp;

-- Schema-level privileges held by the role:
SELECT 'e_mart' AS schema_name,
       has_schema_privilege('ecommerce_role', 'e_mart', 'USAGE')  AS usage_granted,
       has_schema_privilege('ecommerce_role', 'e_mart', 'CREATE') AS create_granted;

-- Effective table privileges for the USER (transitive via role membership):
SELECT schemaname,
       tablename,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'SELECT') AS can_select,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'INSERT') AS can_insert,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'UPDATE') AS can_update,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'DELETE') AS can_delete
FROM   pg_tables
WHERE  schemaname = 'e_mart'
ORDER  BY tablename;

-- Default privileges configured for future objects created by ecommerce_user:
SELECT n.nspname          AS schema_name,
       d.defaclobjtype    AS object_type,   -- 'r' = table, 'S' = sequence
       d.defaclacl        AS default_acl
FROM   pg_default_acl d
JOIN   pg_namespace n ON n.oid = d.defaclnamespace
WHERE  n.nspname = 'e_mart';


-- ============================================================================
-- MINIMUM REQUIRED PRIVILEGES SUMMARY
-- ============================================================================
-- | Object                        | Granted to       | Privilege                              | Purpose                    |
-- |-------------------------------|------------------|----------------------------------------|----------------------------|
-- | Database ecommerce_db         | ecommerce_role   | CONNECT                                | Establish connection       |
-- | Database ecommerce_db         | ecommerce_role   | CREATE                                 | Create schemas             |
-- | Database ecommerce_db         | ecommerce_role   | TEMPORARY                              | Create temp tables         |
-- | Schema e_mart                 | ecommerce_role   | USAGE, CREATE                          | Use schema, create tables  |
-- | Tables in e_mart              | ecommerce_role   | SELECT, INSERT, UPDATE, DELETE,        | DML + FK references        |
-- |                               |                  | REFERENCES                             |                            |
-- | Sequences in e_mart           | ecommerce_role   | USAGE, SELECT                          | Surrogate-key generation   |
-- | (default privileges set       |                  | (auto-applies above to future objects) | No re-grant after setup    |
-- |   via ALTER DEFAULT PRIV)      |                  |                                        |                            |
-- | ecommerce_role                | ecommerce_user   | (membership)                           | Inherit role privileges    |
-- ============================================================================
--
-- NOTE: PART A (role/user/database) must be created by an admin beforehand.
-- `dwh setup-tables` (running as ecommerce_user) creates the e_mart schema
-- and tables; PART B pre-grants privileges so those objects are usable.
-- ============================================================================
