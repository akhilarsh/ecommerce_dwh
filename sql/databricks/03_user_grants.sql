-- ============================================================================
-- DATABRICKS UNITY CATALOG GRANTS FOR ECOMMERCE DWH DEPLOYMENT
-- ============================================================================
--
-- Catalog : ecommerce_db
-- Schemas : e_mart           (DWH tables — Phase 11 deployment target)
--           _rudderstack     (RudderStack ingestion / staging)
-- Group   : ecommerce_role   (Databricks equivalent of a Snowflake role —
--                             grant privileges here, add users as members)
-- User    : ecommerce_user
--
-- Run order:
--   1. Account admin creates ecommerce_role + ecommerce_user        (Section 1)
--   2. Catalog owner creates schemas                                (Section 2)
--   3. Catalog owner runs the GRANTs                                (Sections 3-4)
--   4. Account admin adds ecommerce_user to ecommerce_role          (Section 5)
--   5. Workspace admin grants SQL warehouse access                  (Section 6)
--   6. Anyone verifies                                              (Section 7)
--
-- Sections 1, 5, 6 are NOT pure SQL — Databricks identities and warehouse
-- permissions are managed via the account console / SCIM API / Permissions API,
-- not via UC GRANT statements.
-- ============================================================================


-- ============================================================================
-- 1. CREATE GROUP AND USER  (NOT SQL — account console / CLI / REST API)
-- ============================================================================
-- Databricks does NOT support `CREATE USER` or account-level `CREATE GROUP`
-- via SQL. Account identities are created in one of three ways:
--
--   Option A — Account console UI (simplest):
--     1. https://accounts.cloud.databricks.com  ->  User management
--     2. Groups   -> Add group -> name: ecommerce_role
--     3. Users    -> Add user  -> email/username: ecommerce_user
--
--   Option B — Databricks CLI:
--     databricks account groups create --json '{"displayName": "ecommerce_role"}'
--     databricks account users  create --json '{"userName": "ecommerce_user"}'
--
--   Option C — SCIM REST API:
--     curl -X POST https://accounts.cloud.databricks.com/api/2.0/accounts/<account-id>/scim/v2/Groups \
--       -H "Authorization: Bearer $TOKEN" \
--       -d '{"displayName": "ecommerce_role"}'
--     curl -X POST https://accounts.cloud.databricks.com/api/2.0/accounts/<account-id>/scim/v2/Users \
--       -H "Authorization: Bearer $TOKEN" \
--       -d '{"userName": "ecommerce_user"}'
--
-- The group must then be assigned to the workspace before it can be used in
-- GRANT statements:
--     Account console -> Workspaces -> <workspace> -> Permissions
--       -> Add `ecommerce_role`


-- ============================================================================
-- 2. CREATE SCHEMAS
-- ============================================================================
-- Catalog `ecommerce_db` must already exist (created by a metastore admin).
-- The `_rudderstack` name has a leading underscore so it must be backtick-quoted.

CREATE SCHEMA IF NOT EXISTS `ecommerce_db`.`e_mart`
COMMENT 'E-Commerce data warehouse — dim/fact/bridge tables (Phase 11 deployment target)';

CREATE SCHEMA IF NOT EXISTS `ecommerce_db`.`_rudderstack`
COMMENT 'RudderStack ingestion / staging schema for raw event data';


-- ============================================================================
-- 3. CATALOG PRIVILEGES (granted to the group)
-- ============================================================================
GRANT USE CATALOG    ON CATALOG `ecommerce_db` TO `ecommerce_role`;

-- Optional — only needed if the role should be able to create additional
-- schemas in the future. Skip if e_mart and _rudderstack are the only ones.
GRANT CREATE SCHEMA  ON CATALOG `ecommerce_db` TO `ecommerce_role`;


-- ============================================================================
-- 4. SCHEMA PRIVILEGES (granted to the group)
-- ============================================================================
-- Bundle covering everything the deployment + ingestion pipelines need:
-- USE SCHEMA, CREATE TABLE, SELECT, MODIFY, REFRESH, READ VOLUME, etc.

GRANT ALL PRIVILEGES ON SCHEMA `ecommerce_db`.`e_mart`       TO `ecommerce_role`;
GRANT ALL PRIVILEGES ON SCHEMA `ecommerce_db`.`_rudderstack` TO `ecommerce_role`;

-- OR, grant only what each pipeline actually uses:
-- GRANT USE SCHEMA   ON SCHEMA `ecommerce_db`.`e_mart`       TO `ecommerce_role`;
-- GRANT CREATE TABLE ON SCHEMA `ecommerce_db`.`e_mart`       TO `ecommerce_role`;
-- GRANT SELECT       ON SCHEMA `ecommerce_db`.`e_mart`       TO `ecommerce_role`;
-- GRANT MODIFY       ON SCHEMA `ecommerce_db`.`e_mart`       TO `ecommerce_role`;
-- GRANT USE SCHEMA   ON SCHEMA `ecommerce_db`.`_rudderstack` TO `ecommerce_role`;
-- GRANT CREATE TABLE ON SCHEMA `ecommerce_db`.`_rudderstack` TO `ecommerce_role`;
-- GRANT SELECT       ON SCHEMA `ecommerce_db`.`_rudderstack` TO `ecommerce_role`;
-- GRANT MODIFY       ON SCHEMA `ecommerce_db`.`_rudderstack` TO `ecommerce_role`;


-- ============================================================================
-- TABLE-LEVEL PRIVILEGES (NOT NEEDED — INHERITED FROM SCHEMA)
-- ============================================================================
-- UC permissions inherit, so the schema grants above already cover all
-- existing AND future tables. There is no "GRANT ON FUTURE TABLES" syntax.
--
-- Use these only to override at the table level:
-- GRANT  SELECT ON TABLE `ecommerce_db`.`e_mart`.`dim_customers` TO   `ecommerce_role`;
-- REVOKE MODIFY ON TABLE `ecommerce_db`.`e_mart`.`dim_customers` FROM `ecommerce_role`;


-- ============================================================================
-- 5. ASSIGN ROLE TO USER  (NOT SQL — account console / CLI)
-- ============================================================================
-- Adding `ecommerce_user` to the `ecommerce_role` group is done in the
-- Databricks account console, NOT via SQL.
--
--   Option A — Account console UI:
--     Account console > User management > Groups > ecommerce_role
--       Add member -> ecommerce_user
--
--   Option B — Databricks CLI:
--     databricks account groups patch <group-id> --json '{
--       "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
--       "Operations": [{
--         "op": "add",
--         "path": "members",
--         "value": [{"value": "<user-id>"}]
--       }]
--     }'
--
-- Once `ecommerce_user` is a member of `ecommerce_role`, the user inherits
-- every privilege granted to the group.


-- ============================================================================
-- 6. SQL WAREHOUSE ACCESS  (NOT SQL — workspace UI / Permissions API)
-- ============================================================================
-- The SQL warehouse is a workspace resource governed by the Permissions API,
-- not Unity Catalog.
--
--   Option A — Workspace UI:
--     SQL > SQL Warehouses > <your-warehouse> > Permissions
--       Add principal `ecommerce_role` -> "Can use"
--
--   Option B — Databricks CLI / REST API:
--     databricks permissions update sql-warehouses <warehouse-id> --json '{
--       "access_control_list": [{
--         "group_name": "ecommerce_role",
--         "permission_level": "CAN_USE"
--       }]
--     }'


-- ============================================================================
-- 7. VERIFY
-- ============================================================================
SHOW SCHEMAS IN `ecommerce_db`;
SHOW GRANTS  ON CATALOG `ecommerce_db`;
SHOW GRANTS  ON SCHEMA  `ecommerce_db`.`e_mart`;
SHOW GRANTS  ON SCHEMA  `ecommerce_db`.`_rudderstack`;
SHOW GRANTS  TO         `ecommerce_role`;
SHOW GRANTS  TO         `ecommerce_user`;   -- transitive grants via ecommerce_role


-- ============================================================================
-- MINIMUM REQUIRED PRIVILEGES SUMMARY
-- ============================================================================
-- | Object                              | Privilege        | Purpose                          |
-- |-------------------------------------|------------------|----------------------------------|
-- | SQL Warehouse                       | CAN_USE (UI/API) | Run queries                      |
-- | CATALOG ecommerce_db                | USE CATALOG      | See/use the catalog              |
-- | CATALOG ecommerce_db                | CREATE SCHEMA    | Create future schemas (optional) |
-- | SCHEMA  ecommerce_db.e_mart         | USE SCHEMA       | See/use the DWH schema           |
-- | SCHEMA  ecommerce_db.e_mart         | CREATE TABLE     | Create dim/fact/bridge tables    |
-- | SCHEMA  ecommerce_db.e_mart         | SELECT           | Read tables for validation/BI    |
-- | SCHEMA  ecommerce_db.e_mart         | MODIFY           | INSERT / UPDATE / DELETE / MERGE |
-- | SCHEMA  ecommerce_db._rudderstack   | USE SCHEMA       | See/use the staging schema       |
-- | SCHEMA  ecommerce_db._rudderstack   | CREATE TABLE     | Create raw event tables          |
-- | SCHEMA  ecommerce_db._rudderstack   | SELECT / MODIFY  | Read + write event data          |
-- ============================================================================
