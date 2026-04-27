"""
Gated integration smoke test for Amazon Redshift.

Phase 11/12 lesson: a real round-trip catches SDK type-binding /
paramstyle issues that mocked unit tests cannot. This test creates a
temporary table, loads rows exercising every special data type (BIGINT,
NUMERIC, VARCHAR, TIMESTAMP, SUPER, GEOGRAPHY, VARBYTE, BOOLEAN), reads
them back, and drops the table.

Skipped unless `RUN_REDSHIFT_SMOKE=1` is set AND REDSHIFT_DATABASE is
configured. Provide REDSHIFT_HOST + REDSHIFT_USER + REDSHIFT_PASSWORD
(password mode) or REDSHIFT_AUTH_METHOD=iam with the corresponding
cluster/workgroup vars.

Optionally tests the COPY-from-S3 path when REDSHIFT_S3_STAGING_BUCKET
and REDSHIFT_COPY_IAM_ROLE are also set.

Usage:
    source venv/bin/activate
    export REDSHIFT_HOST=mycluster.abc.us-east-1.redshift.amazonaws.com
    export REDSHIFT_DATABASE=ecommerce_db
    export REDSHIFT_SCHEMA=e_mart            # must already exist
    export REDSHIFT_USER=ecommerce_dwh
    export REDSHIFT_PASSWORD=...
    export AWS_REGION=us-east-1
    export RUN_REDSHIFT_SMOKE=1
    # Optional COPY validation:
    export REDSHIFT_S3_STAGING_BUCKET=your-staging-bucket
    export REDSHIFT_COPY_IAM_ROLE=arn:aws:iam::1234:role/copy-role
    pytest tests/test_redshift_smoke.py -v
"""

import base64
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REDSHIFT_SMOKE") != "1" or not os.getenv("REDSHIFT_DATABASE"),
    reason=(
        "Redshift smoke test gated. Set RUN_REDSHIFT_SMOKE=1 and REDSHIFT_DATABASE "
        "(plus host/user/password or IAM creds) to enable."
    ),
)


@pytest.fixture(scope="module")
def connector():
    from src.connectors.redshift_connector import RedshiftConnector

    conn = RedshiftConnector()
    conn.connect()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def temp_table_name():
    return f"smoke_{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def schema(connector):
    return connector.schema


def _qualified(schema: str, name: str) -> str:
    return f"{schema}.{name}"


def test_create_temp_table(connector, schema, temp_table_name):
    """Create a table exercising every special-type column we care about."""
    qualified = _qualified(schema, temp_table_name)
    create_sql = f"""
        CREATE TABLE {qualified} (
          id BIGINT NOT NULL,
          amount NUMERIC(15,2),
          name VARCHAR(255),
          created_at TIMESTAMP,
          preferences SUPER,
          home_location GEOGRAPHY,
          raw_payload VARBYTE,
          is_active BOOLEAN,
          PRIMARY KEY (id)
        )
        DISTSTYLE AUTO
    """
    connector.execute_query(create_sql)
    connector.commit()


def test_insert_path_round_trip(connector, schema, temp_table_name):
    """INSERT path with SUPER (JSON_PARSE), GEOGRAPHY (ST_GeogFromText), VARBYTE."""
    from src.data_loaders.redshift_loader import RedshiftLoader
    from src.data_loaders.base_loader import LoaderConfig

    # Force the INSERT path to validate it independently of S3 setup.
    os.environ["REDSHIFT_LOADER_MODE"] = "insert"
    try:
        loader = RedshiftLoader(connector, LoaderConfig(validate_after_load=False))

        df = pd.DataFrame({
            "id": [1, 2],
            "amount": [Decimal("12.34"), Decimal("99.99")],
            "name": ["alpha", "beta"],
            "created_at": [datetime(2026, 4, 26, 12, 0, 0), datetime(2026, 4, 26, 13, 0, 0)],
            "preferences": [
                json.dumps({"theme": "dark", "lang": "en"}),
                json.dumps({"theme": "light"}),
            ],
            "home_location": ["POINT(-116.5 30.4)", "POINT(-122.0 37.5)"],
            "raw_payload": [
                base64.b64encode(b"hello").decode("ascii"),
                base64.b64encode(b"world").decode("ascii"),
            ],
            "is_active": [True, False],
        })

        result = loader.load_dataframe(df, temp_table_name)
        assert result.success, f"INSERT load failed: {result.errors}"
        assert result.rows_loaded == 2

        # Round-trip: read back and assert
        rows = connector.execute_query(
            f"SELECT id, amount, name, preferences, "
            f"ST_AsText(home_location), raw_payload, is_active "
            f"FROM {_qualified(schema, temp_table_name)} "
            f"ORDER BY id"
        )
        assert len(rows) == 2
        first = rows[0]
        assert first[0] == 1
        assert str(first[1]) == "12.34"
        assert first[2] == "alpha"
        # SUPER round-trips as JSON-able value
        assert "dark" in str(first[3])
        # GEOGRAPHY -> WKT via ST_AsText
        assert "POINT" in str(first[4])
        # VARBYTE round-trips as bytes (or hex-encoded depending on driver)
        # is_active
        assert first[6] is True
    finally:
        os.environ.pop("REDSHIFT_LOADER_MODE", None)


def test_copy_path_round_trip(connector, schema, temp_table_name):
    """COPY-from-S3 path. Skipped if S3 staging is not configured."""
    if not (
        os.getenv("REDSHIFT_S3_STAGING_BUCKET")
        and os.getenv("REDSHIFT_COPY_IAM_ROLE")
    ):
        pytest.skip(
            "COPY smoke test skipped: REDSHIFT_S3_STAGING_BUCKET / "
            "REDSHIFT_COPY_IAM_ROLE not set."
        )

    from src.data_loaders.redshift_loader import RedshiftLoader
    from src.data_loaders.base_loader import LoaderConfig

    # Force COPY path.
    os.environ["REDSHIFT_LOADER_MODE"] = "copy"
    try:
        # Truncate first so we have a clean baseline for row-count assertion.
        connector.execute_query(
            f"TRUNCATE TABLE {_qualified(schema, temp_table_name)}"
        )
        connector.commit()

        loader = RedshiftLoader(
            connector,
            LoaderConfig(validate_after_load=False),
        )

        df = pd.DataFrame({
            "id": [10, 11, 12],
            "amount": [Decimal("1.00"), Decimal("2.00"), Decimal("3.00")],
            "name": ["a", "b", "c"],
            "created_at": [
                datetime(2026, 4, 26, 12, 0, 0),
                datetime(2026, 4, 26, 12, 5, 0),
                datetime(2026, 4, 26, 12, 10, 0),
            ],
            "preferences": [
                json.dumps({"k": 1}),
                json.dumps({"k": 2}),
                json.dumps({"k": 3}),
            ],
            "home_location": ["POINT(0 0)", "POINT(1 1)", "POINT(2 2)"],
            "raw_payload": [
                base64.b64encode(b"x").decode("ascii"),
                base64.b64encode(b"y").decode("ascii"),
                base64.b64encode(b"z").decode("ascii"),
            ],
            "is_active": [True, True, False],
        })

        result = loader.load_dataframe(df, temp_table_name)
        assert result.success, f"COPY load failed: {result.errors}"
        assert result.rows_loaded == 3

        rows = connector.execute_query(
            f"SELECT COUNT(*) FROM {_qualified(schema, temp_table_name)}"
        )
        assert rows[0][0] == 3
    finally:
        os.environ.pop("REDSHIFT_LOADER_MODE", None)


def test_drop_temp_table(connector, schema, temp_table_name):
    """Cleanup."""
    connector.execute_query(
        f"DROP TABLE IF EXISTS {_qualified(schema, temp_table_name)} CASCADE"
    )
    connector.commit()
