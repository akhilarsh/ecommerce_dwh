-- ============================================================================
-- REDSHIFT USER + ROLE + IAM GRANTS FOR ECOMMERCE DWH DEPLOYMENT
-- ============================================================================
--
-- Database  : ecommerce_db
-- Schema    : e_mart            (DWH tables — Phase 13 deployment target)
-- Role      : ecommerce_role    (collects all privileges; user-agnostic)
-- User      : ecommerce_user    (member of ecommerce_role)
-- Region    : us-east-1
--
-- Naming mirrors Databricks (ecommerce_role / ecommerce_user) and Snowflake
-- conventions so cross-platform docs / scripts stay consistent.
--
-- Two parts:
--   PART A. Database-level GRANTs    (pure SQL, run as a superuser)
--   PART B. AWS IAM setup for COPY   (NOT SQL — IAM console / aws CLI)
--
-- Run order:
--   1. Cluster / workgroup admin creates the role + user                 (Part A.1 - A.2)
--   2. Admin grants schema + table privileges to the role                (Part A.3 - A.5)
--   3. Admin assigns the user to the role                                (Part A.6)
--   4. AWS account admin creates the IAM role + S3 bucket policy         (Part B.1 - B.2)
--   5. Admin attaches the IAM role to the cluster / workgroup            (Part B.3)
--   6. Anyone verifies                                                   (Part A.7 / B.4)
-- ============================================================================


-- ============================================================================
-- PART A. DATABASE-LEVEL GRANTS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- A.1. CREATE THE ROLE  (Redshift native role since 2022)
-- ----------------------------------------------------------------------------
-- A role collects privileges and is granted to one or more users.  Re-running
-- this script is safe: CREATE ROLE IF NOT EXISTS is idempotent.
CREATE ROLE ecommerce_role;


-- ----------------------------------------------------------------------------
-- A.2. CREATE THE DEPLOYMENT USER
-- ----------------------------------------------------------------------------
-- Password is shown for clarity only; for production prefer IAM auth and
-- skip the password entirely (see Part B). The DB user name must match
-- REDSHIFT_USER in your .env.
CREATE USER ecommerce_user WITH PASSWORD 'Ecomm!Strong26';


-- ----------------------------------------------------------------------------
-- A.3. DATABASE-LEVEL PRIVILEGES (ON ROLE)
-- ----------------------------------------------------------------------------
-- IMPORTANT: this script must be run while CONNECTED TO ecommerce_db
-- (e.g. `\c ecommerce_db` in psql). Schemas, role grants, and ALTER DEFAULT
-- PRIVILEGES are all database-scoped — running in the wrong database lands
-- everything in `dev` (or wherever) instead.
--
-- Database-level CREATE lets the role create new schemas; TEMPORARY lets
-- it create temp tables (some query-rewrite paths need them). Redshift
-- does NOT accept USAGE on a database — that's a Postgres-only privilege;
-- on Redshift, a user can connect to any database it has SELECT/CREATE on.
GRANT CREATE, TEMPORARY ON DATABASE ecommerce_db TO ROLE ecommerce_role;


-- ----------------------------------------------------------------------------
-- A.4. CREATE THE SCHEMA  (skip if `dwh setup-tables` will create it)
-- ----------------------------------------------------------------------------
-- Owned by ecommerce_user so the role can fully manage it (CREATE TABLE,
-- DROP TABLE, ALTER TABLE — all require ownership on Redshift).
CREATE SCHEMA IF NOT EXISTS e_mart AUTHORIZATION ecommerce_user;


-- ----------------------------------------------------------------------------
-- A.4b. SCHEMA-LEVEL PRIVILEGES (ON ROLE, NOT ON USER)
-- ----------------------------------------------------------------------------
-- Redundant with AUTHORIZATION ecommerce_user above (the user owns the
-- schema and so does the role transitively), but explicit is clearer and
-- handles the case where the schema was created by a different user.
GRANT USAGE, CREATE ON SCHEMA e_mart TO ROLE ecommerce_role;


-- ----------------------------------------------------------------------------
-- A.5. TABLE-LEVEL PRIVILEGES (ON ROLE)
-- ----------------------------------------------------------------------------
-- Existing tables: grant SELECT/INSERT/UPDATE/DELETE/REFERENCES.
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
ON ALL TABLES IN SCHEMA e_mart TO ROLE ecommerce_role;

-- Future tables: ALTER DEFAULT PRIVILEGES so newly-created tables inherit
-- the same grants without re-running this script.
--
-- `FOR USER ecommerce_user` is REQUIRED — without it, the defaults only
-- apply to tables created by the user running this statement (the
-- superuser), not to tables created later by ecommerce_user via
-- `dwh setup-tables`. Redshift also rejects REFERENCES in this position
-- (only SELECT/INSERT/UPDATE/DELETE/RULE/TRIGGER are accepted).
ALTER DEFAULT PRIVILEGES FOR USER ecommerce_user IN SCHEMA e_mart
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ROLE ecommerce_role;


-- ----------------------------------------------------------------------------
-- A.6. ASSIGN THE ROLE TO THE USER
-- ----------------------------------------------------------------------------
-- All privileges above are now inherited by ecommerce_user transitively.
GRANT ROLE ecommerce_role TO ecommerce_user;


-- ----------------------------------------------------------------------------
-- A.7. VERIFY GRANTS
-- ----------------------------------------------------------------------------
-- Roles granted to the user (membership):
SELECT role_name, admin_option
FROM   svv_user_grants
WHERE  user_name = 'ecommerce_user';

-- Role-to-role membership involving ecommerce_role
-- (svv_role_grants exposes ONLY role_name + granted_role_name — no
-- admin_option, no granted_by; those are user-grant-only columns):
SELECT role_name, granted_role_name
FROM   svv_role_grants
WHERE  role_name = 'ecommerce_role'
   OR  granted_role_name = 'ecommerce_role';

-- Object privileges held by the role (the right view for this is
-- svv_relation_privileges, NOT svv_role_grants):
SELECT namespace_name, relation_name, privilege_type
FROM   svv_relation_privileges
WHERE  identity_name = 'ecommerce_role'
  AND  identity_type = 'role'
ORDER  BY namespace_name, relation_name, privilege_type;

-- Schema-level privileges held by the role:
SELECT namespace_name, privilege_type
FROM   svv_schema_privileges
WHERE  identity_name = 'ecommerce_role'
  AND  identity_type = 'role'
ORDER  BY namespace_name, privilege_type;

-- Database-level privileges held by the role:
SELECT database_name, privilege_type
FROM   svv_database_privileges
WHERE  identity_name = 'ecommerce_role'
  AND  identity_type = 'role'
ORDER  BY database_name, privilege_type;

-- Effective table privileges for the user (transitive via role membership):
SELECT schemaname,
       tablename,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'SELECT') AS can_select,
       has_table_privilege('ecommerce_user', schemaname || '.' || tablename, 'INSERT') AS can_insert
FROM   pg_tables
WHERE  schemaname = 'e_mart'
ORDER  BY tablename;

-- Schema-level privilege resolution for the user (Redshift's pg catalog
-- is forked from PG 8.0 and does NOT have pg_roles — use the helper
-- functions directly with literal names):
SELECT 'e_mart'         AS schema_name,
       'ecommerce_user' AS user_name,
       has_schema_privilege('ecommerce_user', 'e_mart', 'USAGE')  AS usage_granted,
       has_schema_privilege('ecommerce_user', 'e_mart', 'CREATE') AS create_granted;


-- ============================================================================
-- PART B. AWS IAM SETUP FOR COPY-FROM-S3 (NOT SQL)
-- ============================================================================
-- The Redshift COPY command authenticates to S3 via an IAM role attached to
-- the cluster (provisioned) or workgroup (serverless). The role needs
-- s3:GetObject on the staging bucket and (recommended) s3:ListBucket for
-- prefix listing.
--
-- These are AWS IAM resources, not Redshift database privileges, so they
-- can't be granted via SQL.

-- ----------------------------------------------------------------------------
-- B.1. CREATE THE IAM ROLE
-- ----------------------------------------------------------------------------
-- Trust policy must allow `redshift.amazonaws.com` (provisioned) or
-- `redshift-serverless.amazonaws.com` (serverless) to assume the role.
--
--   Option A — aws CLI:
--     aws iam create-role \
--       --role-name ecommerce-dwh-copy-role \
--       --assume-role-policy-document '{
--         "Version": "2012-10-17",
--         "Statement": [{
--           "Effect": "Allow",
--           "Principal": { "Service": "redshift.amazonaws.com" },
--           "Action": "sts:AssumeRole"
--         }]
--       }'
--
--   Option B — IAM Console:
--     IAM > Roles > Create role > AWS service > Redshift > Redshift - Customizable


-- ----------------------------------------------------------------------------
-- B.2. ATTACH AN INLINE POLICY GRANTING S3 ACCESS
-- ----------------------------------------------------------------------------
-- Replace `<your-staging-bucket>` with the bucket configured in
-- REDSHIFT_S3_STAGING_BUCKET. Loader writes objects under
-- s3://<bucket>/<database>/<schema>/<table>/<utc_iso>-<uuid>.json.gz, so
-- scope to that prefix for least-privilege.
--
--   aws iam put-role-policy \
--     --role-name ecommerce-dwh-copy-role \
--     --policy-name s3-staging-access \
--     --policy-document '{
--       "Version": "2012-10-17",
--       "Statement": [
--         {
--           "Effect": "Allow",
--           "Action": ["s3:GetObject", "s3:DeleteObject"],
--           "Resource": "arn:aws:s3:::<your-staging-bucket>/ecommerce_db/e_mart/*"
--         },
--         {
--           "Effect": "Allow",
--           "Action": ["s3:ListBucket"],
--           "Resource": "arn:aws:s3:::<your-staging-bucket>",
--           "Condition": {
--             "StringLike": { "s3:prefix": ["ecommerce_db/e_mart/*"] }
--           }
--         }
--       ]
--     }'


-- ----------------------------------------------------------------------------
-- B.3. ATTACH THE IAM ROLE TO THE CLUSTER / WORKGROUP
-- ----------------------------------------------------------------------------
-- Provisioned cluster:
--   aws redshift modify-cluster-iam-roles \
--     --cluster-identifier ecommerce-dwh-cluster \
--     --add-iam-roles arn:aws:iam::123456789012:role/ecommerce-dwh-copy-role
--
-- Serverless workgroup:
--   aws redshift-serverless update-workgroup \
--     --workgroup-name ecommerce-dwh-wg \
--     --iam-role-arns arn:aws:iam::123456789012:role/ecommerce-dwh-copy-role


-- ----------------------------------------------------------------------------
-- B.4. RECOMMENDED: BUCKET LIFECYCLE RULE
-- ----------------------------------------------------------------------------
-- The loader deletes staged objects on COPY success but leaves them on
-- failure for post-mortem. A 1-day expiration on the staging prefix reaps
-- any stragglers automatically.
--
--   aws s3api put-bucket-lifecycle-configuration \
--     --bucket <your-staging-bucket> \
--     --lifecycle-configuration '{
--       "Rules": [{
--         "ID": "expire-ecommerce-dwh-staging",
--         "Status": "Enabled",
--         "Filter": { "Prefix": "ecommerce_db/e_mart/" },
--         "Expiration": { "Days": 1 }
--       }]
--     }'


-- ============================================================================
-- MINIMUM REQUIRED PRIVILEGES SUMMARY
-- ============================================================================
-- | Object                        | Granted to       | Privilege                              | Purpose                    |
-- |-------------------------------|------------------|----------------------------------------|----------------------------|
-- | Database ecommerce_db         | (default)        | CONNECT (default for any user)         | Establish connection       |
-- | Schema e_mart                 | ecommerce_role   | USAGE, CREATE                          | Use schema, create tables  |
-- | Tables in e_mart              | ecommerce_role   | SELECT, INSERT, UPDATE, DELETE,        | DML + DDL                  |
-- |                               |                  | REFERENCES                             |                            |
-- | (default privileges set       |                  | (auto-applies above to future tables)  | No re-grant needed         |
-- |   via ALTER DEFAULT PRIV)     |                  |                                        |                            |
-- | ecommerce_role                | ecommerce_user   | (membership)                           | Inherit role privileges    |
-- |                               |                  |                                        |                            |
-- | IAM role on cluster/workgroup | (AWS principal)  | s3:GetObject + s3:ListBucket on prefix | COPY-from-S3 ingestion     |
-- |                               |                  | s3:DeleteObject (loader cleanup)       |                            |
-- ============================================================================
