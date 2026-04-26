"""Tests for BigQueryLoader."""

import base64
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


class _SchemaField:
    """Real class for SchemaField — needed because the loader filters on
    the .name attribute, which a MagicMock would not satisfy."""

    def __init__(self, name, field_type, mode="NULLABLE"):
        self.name = name
        self.field_type = field_type
        self.mode = mode


def _install_mock_google_cloud_bigquery():
    """Install fake google.cloud.bigquery so loader imports succeed."""
    if "google.cloud.bigquery" in sys.modules:
        bq = sys.modules["google.cloud.bigquery"]
        # Patch on attributes that may be missing OR overridden as MagicMock
        # by another test file's mock setup. SchemaField in particular MUST
        # be the real-class form for loader filtering to work.
        if not hasattr(bq, "SourceFormat"):
            bq.SourceFormat = types.SimpleNamespace(
                NEWLINE_DELIMITED_JSON="NEWLINE_DELIMITED_JSON",
                PARQUET="PARQUET",
                CSV="CSV",
            )
        bq.SchemaField = _SchemaField
        if not hasattr(bq, "LoadJobConfig"):
            bq.LoadJobConfig = MagicMock()
        return bq

    google_pkg = types.ModuleType("google"); google_pkg.__path__ = []
    cloud_pkg = types.ModuleType("google.cloud"); cloud_pkg.__path__ = []
    google_pkg.cloud = cloud_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.cloud"] = cloud_pkg

    bq = types.ModuleType("google.cloud.bigquery")
    bq.Client = MagicMock()
    bq.QueryJobConfig = MagicMock()
    bq.LoadJobConfig = MagicMock()
    bq.SchemaField = _SchemaField
    bq.ScalarQueryParameter = MagicMock()
    bq.WriteDisposition = types.SimpleNamespace(
        WRITE_APPEND="WRITE_APPEND",
        WRITE_TRUNCATE="WRITE_TRUNCATE",
    )
    bq.SourceFormat = types.SimpleNamespace(
        NEWLINE_DELIMITED_JSON="NEWLINE_DELIMITED_JSON",
        PARQUET="PARQUET",
        CSV="CSV",
    )
    sys.modules["google.cloud.bigquery"] = bq
    cloud_pkg.bigquery = bq

    exc = types.ModuleType("google.cloud.exceptions")

    class NotFound(Exception):
        pass

    exc.NotFound = NotFound
    sys.modules["google.cloud.exceptions"] = exc
    cloud_pkg.exceptions = exc

    oauth2 = types.ModuleType("google.oauth2"); oauth2.__path__ = []
    sa = types.ModuleType("google.oauth2.service_account")
    sa.Credentials = MagicMock()
    sys.modules["google.oauth2"] = oauth2
    sys.modules["google.oauth2.service_account"] = sa
    google_pkg.oauth2 = oauth2

    return bq


_BQ = _install_mock_google_cloud_bigquery()


from src.data_loaders.base_loader import LoaderConfig  # noqa: E402
from src.data_loaders.bigquery_loader import BigQueryLoader  # noqa: E402


@pytest.fixture
def mock_connector():
    conn = MagicMock()
    conn.PLATFORM = "bigquery"
    conn.project = "ecommerce-db"
    conn.dataset = "e_mart"
    conn.location = "US"
    conn.client = MagicMock()

    # Default schema fetch returns a fake table with fields matching the
    # sample_df fixture below. Tests that need a different schema can
    # override conn.client.get_table.return_value.schema.
    fake_table = MagicMock()
    fake_table.schema = [
        _BQ.SchemaField("id", "INT64"),
        _BQ.SchemaField("name", "STRING"),
        _BQ.SchemaField("amount", "NUMERIC"),
    ]
    conn.client.get_table.return_value = fake_table

    conn.client.load_table_from_file = MagicMock()
    conn.execute_query = MagicMock(return_value=[(100,)])
    conn.table_exists = MagicMock(return_value=True)
    return conn


@pytest.fixture
def loader(mock_connector):
    config = LoaderConfig(
        batch_size=5000,
        truncate_before_load=False,
        validate_after_load=False,
    )
    return BigQueryLoader(mock_connector, config)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "amount": [10.5, 20.0, 30.75],
    })


class TestBigQueryLoaderInit:

    def test_platform_name(self, loader):
        assert loader.platform_name == "bigquery"

    def test_inherits_connector_project(self, mock_connector):
        ldr = BigQueryLoader(mock_connector)
        assert ldr.config.database == "ecommerce-db"

    def test_inherits_connector_dataset(self, mock_connector):
        ldr = BigQueryLoader(mock_connector)
        assert ldr.config.schema == "e_mart"


class TestLoadDataframe:

    def test_load_dispatches_to_load_job(self, loader, sample_df, mock_connector):
        load_job = MagicMock()
        load_job.output_rows = 3
        load_job.result = MagicMock()
        mock_connector.client.load_table_from_file.return_value = load_job

        result = loader.load_dataframe(sample_df, "test_table")

        assert result.success is True
        assert result.rows_loaded == 3
        mock_connector.client.load_table_from_file.assert_called_once()

    def test_load_uses_three_part_qualified_name(self, loader, sample_df, mock_connector):
        load_job = MagicMock()
        load_job.output_rows = 3
        mock_connector.client.load_table_from_file.return_value = load_job

        loader.load_dataframe(sample_df, "dim_customers")

        args, kwargs = mock_connector.client.load_table_from_file.call_args
        # second positional arg is the destination table
        assert args[1] == "ecommerce-db.e_mart.dim_customers"

    def test_load_passes_location_to_job(self, loader, sample_df, mock_connector):
        load_job = MagicMock()
        load_job.output_rows = 3
        mock_connector.client.load_table_from_file.return_value = load_job

        loader.load_dataframe(sample_df, "dim_customers")

        kwargs = mock_connector.client.load_table_from_file.call_args.kwargs
        assert kwargs.get("location") == "US"

    def test_special_columns_serialized_correctly(self, mock_connector):
        load_job = MagicMock()
        load_job.output_rows = 1
        mock_connector.client.load_table_from_file.return_value = load_job

        # Override the table schema to match this DataFrame's columns.
        fake_table = MagicMock()
        fake_table.schema = [
            _BQ.SchemaField("customer_key", "INT64"),
            _BQ.SchemaField("customer_preferences", "JSON"),
            _BQ.SchemaField("home_location", "GEOGRAPHY"),
            _BQ.SchemaField("raw_payload", "BYTES"),
        ]
        mock_connector.client.get_table.return_value = fake_table

        df = pd.DataFrame({
            "customer_key": [1],
            "customer_preferences": ['{"foo": "bar"}'],
            "home_location": ["POINT(-1 1)"],
            "raw_payload": [base64.b64encode(b"hello").decode()],
        })

        ldr = BigQueryLoader(
            mock_connector,
            LoaderConfig(validate_after_load=False),
        )
        ldr.load_dataframe(df, "fact_customer_interactions")

        # First positional arg is the BytesIO with NDJSON contents.
        ndjson_io = mock_connector.client.load_table_from_file.call_args.args[0]
        ndjson_io.seek(0)
        line = ndjson_io.read().decode("utf-8").strip()
        import json as _json
        doc = _json.loads(line)

        # JSON column: should be a parsed dict, not a string.
        assert doc["customer_preferences"] == {"foo": "bar"}
        # GEOGRAPHY: WKT string passes through.
        assert doc["home_location"] == "POINT(-1 1)"
        # BYTES: base64 ASCII string preserved.
        assert doc["raw_payload"] == base64.b64encode(b"hello").decode()

    def test_empty_df_returns_validation_error(self, loader, mock_connector):
        result = loader.load_dataframe(pd.DataFrame(), "test_table")
        assert result.success is False
        assert len(result.errors) > 0
        mock_connector.client.load_table_from_file.assert_not_called()

    def test_truncate_before_load(self, mock_connector, sample_df):
        load_job = MagicMock()
        load_job.output_rows = 3
        mock_connector.client.load_table_from_file.return_value = load_job

        config = LoaderConfig(truncate_before_load=True, validate_after_load=False)
        ldr = BigQueryLoader(mock_connector, config)
        ldr.load_dataframe(sample_df, "test_table")

        truncate_calls = [
            c for c in mock_connector.execute_query.call_args_list
            if "TRUNCATE" in str(c)
        ]
        assert len(truncate_calls) > 0

    def test_load_failure_returns_failed_result(self, loader, sample_df, mock_connector):
        mock_connector.client.load_table_from_file.side_effect = (
            RuntimeError("BQ load failed")
        )
        result = loader.load_dataframe(sample_df, "test_table")
        assert result.success is False
        assert "BQ load failed" in result.errors[0]


class TestLoadCsv:

    def test_file_not_found(self, loader):
        result = loader.load_csv(Path("/nonexistent/file.csv"), "test_table")
        assert result.success is False
        assert "not found" in result.errors[0].lower()

    def test_csv_load_dispatches_through_dataframe_path(self, loader, mock_connector, tmp_path):
        load_job = MagicMock()
        load_job.output_rows = 2
        mock_connector.client.load_table_from_file.return_value = load_job

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Alice\n2,Bob\n")

        result = loader.load_csv(csv_file, "test_table")

        assert result.success is True
        mock_connector.client.load_table_from_file.assert_called_once()


class TestTruncateTable:

    def test_truncate_uses_three_part_name(self, loader, mock_connector):
        loader.truncate_table("dim_customers")
        mock_connector.execute_query.assert_called_with(
            "TRUNCATE TABLE `ecommerce-db.e_mart.dim_customers`"
        )


class TestTableExists:

    def test_delegates_to_connector(self, loader, mock_connector):
        assert loader.table_exists("dim_customers") is True
        mock_connector.table_exists.assert_called_once_with(
            "dim_customers", schema="e_mart"
        )


class TestGetRowCount:

    def test_returns_count(self, loader, mock_connector):
        mock_connector.execute_query.return_value = [(42,)]
        assert loader.get_row_count("dim_customers") == 42
