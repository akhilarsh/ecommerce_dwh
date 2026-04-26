# Phase 12: BigQuery Support

## Overview

Add Google BigQuery as the fourth first-class warehouse target alongside Snowflake, PostgreSQL, and Databricks. Mirrors the Phase 10/11 pattern: new connector, new loader, new DDL adapter, factory registrations, CLI wiring — no changes to existing platforms.

**Scope:** All 23 tables including the customer dimension split and the unsupported-type columns (VARIANT, GEOGRAPHY, BINARY).

## Status: Implemented + smoke test passed against real BigQuery (2026-04-26)

---

## Lessons applied from Phase 11 (Databricks)

To avoid another multi-cycle debug:

1. **Validate against real BigQuery before declaring done.** A one-shot smoke test (create temp table → insert one row with all special types → select back → drop) runs in seconds and catches paramstyle / type-binding issues that mocks can't.
2. **Default to load-job pattern, not row-by-row INSERT.** BigQuery has rate limits and round-trip costs that make iterative INSERTs catastrophically slow for fact tables. The official `load_table_from_dataframe` uses load jobs (free, fast, batched) under the hood.
3. **Read the SDK paramstyle/type-binding docs before picking an approach.** BigQuery's Python client uses query parameters with explicit types, very different from DBAPI-style.

---

## Design

Four new modules, one adapter, factory registrations.

**BigQueryConnector** — wraps `google-cloud-bigquery` Client. Project + dataset model the catalog/schema pair. Auth via service account JSON (most common in production) with ADC fallback for local dev. `commit()`/`rollback()` are no-ops (BigQuery has no client-side transactions; DDL/DML autocommits). Implements `BaseConnector` so factories work unchanged.

Auth (precedence: explicit param → env var → ADC):

| Var | Purpose |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key (standard Google env var) |
| `BIGQUERY_PROJECT` | GCP project id |
| `BIGQUERY_DATASET` | Dataset name (default `ecommerce_dwh`) |
| `BIGQUERY_LOCATION` | Dataset location, e.g. `US`, `EU`, `us-central1` |

**BigQueryLoader** — uses **load jobs** for all sizes via `Client.load_table_from_dataframe(...)`:

| Strategy | Trigger | Method |
|---|---|---|
| Load job (write_truncate / write_append) | Always | `load_table_from_dataframe` with explicit schema |

No row-by-row INSERT path. Load jobs handle 1 row through 100M rows efficiently. Free up to BigQuery's load-job quota (1500 loads per table per day, way more than we need).

For columns the DataFrame can't represent natively (`GEOGRAPHY`, `JSON`, `BYTES`), the loader transforms before upload:
- `home_location`, `geo_location` (text WKT) → loaded as `STRING`, then `UPDATE` to `ST_GEOGFROMTEXT(...)` cast — OR loaded directly as GEOGRAPHY using BigQuery's WKT auto-parse on load. **Decision needed.**
- `customer_preferences`, `event_properties`, `order_tags`, `shipment_metadata` (JSON strings) → loaded into `JSON` column directly; BigQuery parses on ingest.
- `raw_payload` (base64 ASCII) → decoded to bytes before load → uploaded as `BYTES`.

**BqDDLAdapter** — stateless functions transforming `BaseTable` → BigQuery DDL.

Type mapping:

| Snowflake | BigQuery |
|---|---|
| `NUMBER(38,0)` | `INT64` |
| `NUMBER(p,0)` p ≤ 18 | `INT64` |
| `NUMBER(p,0)` p > 18 | `BIGNUMERIC(p)` |
| `NUMBER(p,s)` s > 0 | `NUMERIC(p,s)` |
| `VARCHAR(n)` | `STRING` (length dropped — BigQuery STRING is unbounded) |
| `TIMESTAMP_NTZ` | `DATETIME` |
| `TIMESTAMP` | `TIMESTAMP` |
| `DATE`, `TIME`, `BOOLEAN` | passthrough |
| `FLOAT` | `FLOAT64` |
| `VARIANT`, `OBJECT`, `ARRAY` | `JSON` (native, no parse_json wrapper needed at insert) |
| `BINARY` | `BYTES` |
| `GEOGRAPHY` | `GEOGRAPHY` (native — BigQuery is the only target with first-class geo) |

3-part qualified names: `` `project.dataset.table` `` (backticked).

PK/FK as **informational constraints** (`PRIMARY KEY (...) NOT ENFORCED`, `FOREIGN KEY (...) REFERENCES ... NOT ENFORCED`) — supported on BigQuery since 2023, used by query optimizer and BI tools.

DEFAULT values: BigQuery supports column defaults natively (no `TBLPROPERTIES` workaround like Databricks).

Comments emitted via `OPTIONS (description = '...')` on table and per-column.

**Connector Factory** — adds `bq` / `bigquery` to `DWH_REGISTRY`. The placeholder comments become real imports.

**Loader Factory** — adds `platform == "bigquery"` branch.

**CLI** — `--wh bq` / `--wh bigquery`. No new flags.

---

## Files to Change

| File | Change |
|---|---|
| `src/connectors/bigquery_connector.py` | New |
| `src/data_loaders/bigquery_loader.py` | New |
| `src/sql_generator/bq_ddl_adapter.py` | New |
| `src/connectors/factory.py` | Register `bq` / `bigquery` |
| `src/data_loaders/factory.py` | Add `bigquery` branch |
| `src/connectors/__init__.py` | Export `BigQueryConnector` |
| `src/data_loaders/__init__.py` | Export `BigQueryLoader` |
| `src/cli/main.py` | List BigQuery as supported (not placeholder) |
| `src/cli/commands/generate_sql.py` | `--wh bq` routes to `bq_ddl_adapter`, add `bigquery` to `--all` |
| `src/cli/commands/validate.py` | Add `is_bigquery` branch (3-part naming, INFORMATION_SCHEMA quirks) |
| `src/sql_generator/schema_manager.py` | `_save_bq_scripts` |
| `src/table_manager/create_tables.py` | BigQuery verification + creation path |
| `src/workflows/table_setup_workflow.py` | BigQuery view dir, drop syntax |
| `.env.example` | `GOOGLE_APPLICATION_CREDENTIALS`, `BIGQUERY_*` vars |
| `pyproject.toml` | Add `bigquery` optional extra |
| `plans/PLAN.md` | Phase 12 row |
| `tests/test_bigquery_connector.py` | New, ~12 tests, mocked SDK |
| `tests/test_bigquery_loader.py` | New, ~10 tests |
| `tests/test_bq_ddl_adapter.py` | New, ~25 tests |
| `tests/test_bigquery_smoke.py` | **New — gated integration test against real BigQuery** |

---

## Dependencies

Add to `pyproject.toml`:

```toml
bigquery = [
    "google-cloud-bigquery>=3.20.0",
    "google-cloud-bigquery-storage>=2.24.0",   # faster Arrow-based load_table_from_dataframe
    "pyarrow>=14.0.0",                         # already pinned for Databricks; keep
    "db-dtypes>=1.2.0",                        # required for BigQuery DataFrame I/O
]
```

---

## Decisions needed before implementation

These are the spots where there's a real tradeoff or external constraint I can't decide alone:

### 1. Loading method confirmation

**Recommendation:** `load_table_from_dataframe` with WRITE_APPEND. Free, fast, handles all sizes.

**Alternative:** Streaming inserts via `insert_rows_json`. Real-time but costs $0.01 per 200MB and not needed for batch loads.

Going with the recommendation unless you have a reason to use streaming.

### 2. GEOGRAPHY column ingestion

The data generator produces WKT text like `POINT(-116.5386 30.3991)`. Two ways to land that in a `GEOGRAPHY` column:

- **(A)** Load as `STRING`, then `UPDATE table SET col = ST_GEOGFROMTEXT(col)` after load — clean DataFrame upload, two-step load.
- **(B)** Use BigQuery's auto-parse: when loading via load job, WKT strings are accepted directly into `GEOGRAPHY` columns. One step, but requires explicit schema with the column typed as `GEOGRAPHY`.

**Recommendation: (B).** Cleaner, faster, matches how the data generator already produces values.

### 3. Service account or ADC for the smoke test

To do the round-trip integration test (Phase 11 lesson), I need credentials that can create/drop a temp table in some dataset.

- **(A)** You provide a service account JSON path via `GOOGLE_APPLICATION_CREDENTIALS` and a project/dataset. I run the smoke test once before declaring done.
- **(B)** You skip the smoke test and we proceed on unit tests + your integration validation.

**Recommendation: (A).** It's the only way to catch SDK-version-specific issues (the kind that bit us in Phase 11).

### 4. Project + dataset values for `.env`

What should I use as the example values in `.env.example` and as the actual targets for your run? For consistency with `ecommerce_db.e_mart` on Databricks, I'd suggest:

- `BIGQUERY_PROJECT=<your-gcp-project-id>` — you fill in
- `BIGQUERY_DATASET=ecommerce_dwh` (or `e_mart` for parity)
- `BIGQUERY_LOCATION=US`

Confirm or adjust.

---

## Deliverables

- [x] `src/connectors/bigquery_connector.py`
- [x] `src/sql_generator/bq_ddl_adapter.py`
- [x] `src/data_loaders/bigquery_loader.py`
- [x] Factory registrations (connector + loader)
- [x] CLI/schema_manager/table_manager/workflow wiring
- [x] `.env.example` + `pyproject.toml` extra
- [x] Unit tests (~47 total, mocked SDK)
- [x] **Integration smoke test against real BigQuery — 4/4 pass** (round-trip on INT64, NUMERIC, STRING, DATETIME, JSON, GEOGRAPHY, BYTES, BOOL)
- [x] `plans/PLAN.md` — Phase 12 row
- [x] `sql/bigquery/03_user_grants.sql` — IAM roles + dataset access (analogous to Snowflake/Databricks grants)

### Decisions resolved

1. Loading method: **load jobs via NEWLINE_DELIMITED_JSON source format** (chosen over `load_table_from_dataframe` after the smoke test exposed a "Unsupported field type: JSON" error in the Parquet upload path — Parquet doesn't have a JSON type, but NDJSON loads support every BQ type natively).
2. GEOGRAPHY ingestion: **(B)** explicit GEOGRAPHY schema; BigQuery auto-parses WKT on load.
3. Smoke test: **(A)** ran against real BigQuery and passed.
4. `.env.example` defaults: `BIGQUERY_PROJECT=ecommerce-db`, `BIGQUERY_DATASET=e_mart`, `BIGQUERY_LOCATION=US`.

### Smoke-test surprises (fixed during real BigQuery validation)

1. **`CONSTRAINT name PRIMARY KEY (...) NOT ENFORCED` is rejected inline.** BigQuery only accepts the unnamed `PRIMARY KEY (...) NOT ENFORCED` form within a CREATE TABLE column list, despite the docs grammar implying otherwise. Adapter and smoke test updated.
2. **`load_table_from_dataframe` (Parquet) cannot load JSON columns.** Switched the entire loader to NDJSON source format with explicit per-row JSON encoding (Decimal → str, bytes → base64, datetime → ISO 8601, JSON-string → parsed dict).
3. **DataFrame autodetect maps Python floats to FLOAT64**, conflicting with NUMERIC(p,s) target columns. Fixed by fetching the destination table's schema and using it as the load job's explicit schema (also lets us identify JSON / NUMERIC / DATETIME columns and serialize each correctly).
4. **NUMERIC columns must be encoded as Decimal/string**, not float — Parquet/Arrow path produces "Got bytestring of length 8 (expected 16)" for raw float64 against NUMERIC. NDJSON encoding uses string form to preserve precision.

---

**Version:** 1.0
**Last Updated:** 2026-04-26
**Status:** Awaiting answers to the four decisions above
