"""
Gated integration smoke test for BigQuery.

Phase 11 lesson: a real round-trip catches SDK type-binding / paramstyle
issues that mocked unit tests cannot. This test creates a temporary table,
loads one row exercising every special data type (INT64, NUMERIC, STRING,
DATETIME, JSON, GEOGRAPHY, BYTES, BOOL), reads it back, and drops it.

Skipped unless `RUN_BIGQUERY_SMOKE=1` is set AND BIGQUERY_PROJECT is
configured. Provide GOOGLE_APPLICATION_CREDENTIALS or run after
`gcloud auth application-default login`.

Usage:
    source venv/bin/activate
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    export BIGQUERY_PROJECT=ecommerce-db
    export BIGQUERY_DATASET=e_mart           # must already exist
    export BIGQUERY_LOCATION=US
    export RUN_BIGQUERY_SMOKE=1
    pytest tests/test_bigquery_smoke.py -v
"""

import base64
import json
import os
import time
import uuid
from datetime import datetime

import pandas as pd
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BIGQUERY_SMOKE") != "1" or not os.getenv("BIGQUERY_PROJECT"),
    reason=(
        "BigQuery smoke test gated. Set RUN_BIGQUERY_SMOKE=1 and BIGQUERY_PROJECT "
        "(plus GOOGLE_APPLICATION_CREDENTIALS or ADC) to enable."
    ),
)


@pytest.fixture(scope="module")
def connector():
    from src.connectors.bigquery_connector import BigQueryConnector

    conn = BigQueryConnector()
    conn.connect()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def temp_table_name():
    """Unique throwaway table name; the test cleans it up via DROP TABLE."""
    return f"smoke_{uuid.uuid4().hex[:12]}"


def _qualified(connector, name: str) -> str:
    return f"`{connector.project}.{connector.dataset}.{name}`"


def test_create_temp_table(connector, temp_table_name):
    """Create a table that exercises every special-type column we care about."""
    qualified = _qualified(connector, temp_table_name)
    # BigQuery rejects `CONSTRAINT name PRIMARY KEY` inline; use the unnamed
        # form. (The DDL adapter does the same.)
    create_sql = f"""
        CREATE TABLE {qualified} (
          id INT64 NOT NULL,
          amount NUMERIC(15,2),
          name STRING,
          created_at DATETIME,
          preferences JSON,
          home_location GEOGRAPHY,
          raw_payload BYTES,
          is_active BOOL,
          PRIMARY KEY (id) NOT ENFORCED
        )
    """
    connector.execute_query(create_sql)

    # Confirm visibility through INFORMATION_SCHEMA.
    rows = connector.execute_query(
        f"SELECT table_name FROM "
        f"`{connector.project}.{connector.dataset}.INFORMATION_SCHEMA.TABLES` "
        f"WHERE table_name = '{temp_table_name}'"
    )
    assert rows and rows[0][0] == temp_table_name


def test_load_one_row_exercising_special_types(connector, temp_table_name):
    """Round-trip a row through `load_table_from_dataframe`."""
    from src.data_loaders.bigquery_loader import BigQueryLoader
    from src.data_loaders.base_loader import LoaderConfig

    loader = BigQueryLoader(connector, LoaderConfig(validate_after_load=True))

    df = pd.DataFrame([{
        "id": 1,
        "amount": 1234.56,
        "name": "smoke",
        "created_at": datetime(2026, 4, 26, 12, 34, 56),
        "preferences": json.dumps({"channel": "email", "tier": "gold"}),
        "home_location": "POINT(-122.4194 37.7749)",
        "raw_payload": base64.b64encode(b"hello smoke").decode(),
        "is_active": True,
    }])

    result = loader.load_dataframe(df, temp_table_name)

    assert result.success, f"load failed: {result.errors}"
    assert result.rows_loaded == 1


def test_select_back(connector, temp_table_name):
    """Read the row back and verify the special-type values survived ingestion."""
    qualified = _qualified(connector, temp_table_name)

    # Loads can take a moment to be queryable on small datasets — small retry.
    deadline = time.time() + 30
    rows = []
    while time.time() < deadline:
        rows = connector.execute_query(
            f"""
            SELECT
              id,
              amount,
              name,
              created_at,
              JSON_VALUE(preferences, '$.channel') AS channel,
              ST_ASTEXT(home_location) AS wkt,
              raw_payload,
              is_active
            FROM {qualified}
            """
        )
        if rows:
            break
        time.sleep(2)

    assert rows, "no rows returned from temp table within 30s"
    row = rows[0]
    assert row[0] == 1
    # NUMERIC arrives as a Decimal-like; coerce to float for comparison.
    assert float(row[1]) == 1234.56
    assert row[2] == "smoke"
    # DATETIME arrives as a Python datetime.
    assert isinstance(row[3], datetime)
    assert row[4] == "email"
    assert "POINT" in row[5]
    assert row[6] == b"hello smoke"
    assert row[7] is True


def test_drop_temp_table(connector, temp_table_name):
    qualified = _qualified(connector, temp_table_name)
    connector.execute_query(f"DROP TABLE IF EXISTS {qualified}")

    rows = connector.execute_query(
        f"SELECT table_name FROM "
        f"`{connector.project}.{connector.dataset}.INFORMATION_SCHEMA.TABLES` "
        f"WHERE table_name = '{temp_table_name}'"
    )
    assert not rows
