-- ============================================================================
-- BIGQUERY IAM GRANTS FOR ECOMMERCE DWH DEPLOYMENT
-- ============================================================================
--
-- Project  : ecommerce-db
-- Dataset  : e_mart            (DWH tables — Phase 12 deployment target)
-- Location : US
--
-- Service account (recommended for programmatic deployment + ingestion):
--          ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com
--
-- Run order:
--   1. Project owner / IAM admin creates the service account            (Section 1)
--   2. Project owner grants project-level roles                         (Section 2)
--   3. Dataset owner creates the dataset (or `setup-tables` does it)    (Section 3)
--   4. Dataset owner grants dataset-level roles                         (Section 4)
--   5. Anyone verifies                                                  (Section 5)
--
-- Sections 1, 2, 4 are NOT pure SQL — BigQuery IAM is managed via the
-- Cloud Console, `gcloud` CLI, or `bq` CLI rather than GRANT statements.
-- BigQuery does support GRANT statements for *dataset / table-level* access
-- via INFORMATION_SCHEMA grants — those are shown alongside the gcloud
-- equivalents below.
-- ============================================================================


-- ============================================================================
-- 1. CREATE SERVICE ACCOUNT  (NOT SQL — gcloud / Console / Terraform)
-- ============================================================================
-- Service accounts are GCP IAM identities, not BigQuery objects, so they are
-- created outside SQL.
--
--   Option A — gcloud CLI:
--     gcloud iam service-accounts create ecommerce-dwh \
--       --project=ecommerce-db \
--       --display-name="E-Commerce DWH deployment + ingestion SA"
--
--     gcloud iam service-accounts keys create ~/ecommerce-dwh-key.json \
--       --iam-account=ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com
--
--   Option B — Cloud Console:
--     IAM & Admin > Service Accounts > + CREATE SERVICE ACCOUNT
--       Name: ecommerce-dwh
--       Project: ecommerce-db
--     Then: <service account> > Keys > ADD KEY > Create new key (JSON)
--
-- Save the JSON key path to GOOGLE_APPLICATION_CREDENTIALS in .env.


-- ============================================================================
-- 2. PROJECT-LEVEL ROLES  (NOT SQL — gcloud / Console)
-- ============================================================================
-- Required project-level roles for the deployment service account:
--
--   roles/bigquery.jobUser    — submit query / load / extract / copy jobs
--                               (needed for *every* operation, including SELECT)
--
-- These cannot be granted with GRANT statements; use gcloud or Console.
--
--   Option A — gcloud CLI:
--     gcloud projects add-iam-policy-binding ecommerce-db \
--       --member="serviceAccount:ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com" \
--       --role="roles/bigquery.jobUser"
--
--   Option B — Cloud Console:
--     IAM & Admin > IAM > +GRANT ACCESS
--       Principal: ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com
--       Role: BigQuery Job User


-- ============================================================================
-- 3. CREATE DATASET
-- ============================================================================
-- Project `ecommerce-db` must already exist. The dataset can be created via
-- SQL (`CREATE SCHEMA`), gcloud, or the BigQuery Console. The Phase 12
-- `dwh setup-tables` workflow creates it automatically when missing, but the
-- explicit DDL is shown for documentation.

CREATE SCHEMA IF NOT EXISTS `ecommerce-db.e_mart`
OPTIONS (
  location = 'US',
  description = 'E-Commerce data warehouse — dim/fact/bridge tables (Phase 12 deployment target)'
);


-- ============================================================================
-- 4. DATASET-LEVEL ACCESS
-- ============================================================================
-- Two equivalent approaches are shown — pick one. Dataset-level grants are
-- enough for normal operation; project-level `roles/bigquery.dataEditor` is
-- *broader* (grants access to every dataset in the project) and usually
-- not what you want.
--
-- Option A — SQL GRANT (BigQuery 2023+):

GRANT `roles/bigquery.dataEditor`
ON SCHEMA `ecommerce-db.e_mart`
TO "serviceAccount:ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com";

-- Option B — bq CLI / Console:
--   bq update --source <(jq '.access += [{
--     "role": "roles/bigquery.dataEditor",
--     "userByEmail": "ecommerce-dwh@ecommerce-db.iam.gserviceaccount.com"
--   }]' <(bq show --format=prettyjson ecommerce-db:e_mart)) ecommerce-db:e_mart
--
-- Or via the Console:
--   BigQuery > <dataset> > Sharing > Permissions > +ADD PRINCIPAL


-- ============================================================================
-- TABLE-LEVEL PRIVILEGES (NOT NEEDED — INHERITED FROM DATASET)
-- ============================================================================
-- Dataset-level access propagates to every existing AND future table in the
-- dataset. Use table-level grants only to override or restrict at the table
-- level:
--
-- GRANT `roles/bigquery.dataViewer`
-- ON TABLE `ecommerce-db.e_mart.dim_customers`
-- TO "serviceAccount:read-only-bi@ecommerce-db.iam.gserviceaccount.com";


-- ============================================================================
-- 5. VERIFY
-- ============================================================================
-- Inspect dataset and grants:

SELECT schema_name, location, creation_time
FROM `ecommerce-db.INFORMATION_SCHEMA.SCHEMATA`
WHERE schema_name = 'e_mart';

-- Dataset-level grants live in INFORMATION_SCHEMA.OBJECT_PRIVILEGES:
SELECT object_name, privilege_type, grantee
FROM `ecommerce-db.e_mart.INFORMATION_SCHEMA.OBJECT_PRIVILEGES`
ORDER BY object_name, privilege_type;

-- Or check via gcloud:
--   bq show --format=prettyjson ecommerce-db:e_mart


-- ============================================================================
-- MINIMUM REQUIRED PRIVILEGES SUMMARY
-- ============================================================================
-- | Object                              | Role                      | Purpose                          |
-- |-------------------------------------|---------------------------|----------------------------------|
-- | Project ecommerce-db                | roles/bigquery.jobUser    | Run query / load / extract jobs  |
-- | Dataset ecommerce-db.e_mart         | roles/bigquery.dataEditor | Create/read/modify tables + data |
-- |                                     |                           | (covers SELECT + INSERT + DDL)   |
-- |                                     |                           |                                  |
-- | (optional) Project ecommerce-db     | roles/storage.objectViewer| If loading from GCS via Storage  |
-- |                                     |                           | Read API for fast load jobs      |
-- ============================================================================
