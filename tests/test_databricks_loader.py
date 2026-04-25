"""Tests for DatabricksLoader."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _install_mock_databricks_sql():
    if "databricks.sql" in sys.modules:
        return
    fake_databricks = types.ModuleType("databricks")
    fake_sql = types.ModuleType("databricks.sql")
    fake_sql.connect = MagicMock()
    fake_databricks.sql = fake_sql
    sys.modules["databricks"] = fake_databricks
    sys.modules["databricks.sql"] = fake_sql


_install_mock_databricks_sql()


from src.data_loaders.base_loader import LoaderConfig  # noqa: E402
from src.data_loaders.databricks_loader import DatabricksLoader  # noqa: E402


@pytest.fixture
def mock_connector():
    conn = MagicMock()
    conn.PLATFORM = "databricks"
    conn.catalog = "main"
    conn.database = "main"
    conn.schema = "ecommerce_dwh"
    conn.cursor = MagicMock()
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
    return DatabricksLoader(mock_connector, config)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "amount": [10.5, 20.0, 30.75],
    })


class TestDatabricksLoaderInit:

    def test_platform_name(self, loader):
        assert loader.platform_name == "databricks"

    def test_inherits_connector_catalog(self, mock_connector):
        ldr = DatabricksLoader(mock_connector)
        assert ldr.config.database == "main"

    def test_inherits_connector_schema(self, mock_connector):
        ldr = DatabricksLoader(mock_connector)
        assert ldr.config.schema == "ecommerce_dwh"


class TestLoadDataframe:

    def test_small_df_inline_insert(self, loader, sample_df, mock_connector):
        result = loader.load_dataframe(sample_df, "test_table")

        assert result.success is True
        assert result.rows_loaded == 3
        # Inline INSERT path uses execute(), not executemany()
        mock_connector.cursor.execute.assert_called()
        mock_connector.cursor.executemany.assert_not_called()

    def test_insert_sql_has_three_part_name(self, loader, sample_df, mock_connector):
        loader.load_dataframe(sample_df, "dim_customers")
        insert_sql = mock_connector.cursor.execute.call_args[0][0]
        assert "main.ecommerce_dwh.dim_customers" in insert_sql
        assert insert_sql.startswith("INSERT INTO")
        assert "VALUES" in insert_sql

    def test_inline_values_no_placeholders(self, loader, sample_df, mock_connector):
        loader.load_dataframe(sample_df, "dim_customers")
        insert_sql = mock_connector.cursor.execute.call_args[0][0]
        # Inline values — no ? or :p placeholders
        assert "?" not in insert_sql
        assert ":p" not in insert_sql
        # Real values appear in the SQL
        assert "'Alice'" in insert_sql
        assert "'Bob'" in insert_sql

    def test_nan_rendered_as_null(self, loader, mock_connector):
        df = pd.DataFrame({"id": [1, 2], "val": [10.0, float("nan")]})
        loader.load_dataframe(df, "test_table")

        insert_sql = mock_connector.cursor.execute.call_args[0][0]
        # Second row's val should be NULL
        assert "(2, NULL)" in insert_sql

    def test_empty_df_returns_validation_error(self, loader, mock_connector):
        result = loader.load_dataframe(pd.DataFrame(), "test_table")
        assert result.success is False
        assert len(result.errors) > 0
        mock_connector.cursor.execute.assert_not_called()

    def test_truncate_before_load(self, mock_connector, sample_df):
        config = LoaderConfig(truncate_before_load=True, validate_after_load=False)
        ldr = DatabricksLoader(mock_connector, config)
        ldr.load_dataframe(sample_df, "test_table")

        truncate_calls = [
            c for c in mock_connector.execute_query.call_args_list
            if "TRUNCATE" in str(c)
        ]
        assert len(truncate_calls) > 0

    def test_batched_load_chunks_by_batch_size(self, mock_connector):
        config = LoaderConfig(batch_size=2, validate_after_load=False)
        ldr = DatabricksLoader(mock_connector, config)
        df = pd.DataFrame({"id": list(range(5))})

        result = ldr.load_dataframe(df, "big_table")

        assert result.success is True
        assert result.rows_loaded == 5
        # 5 rows / 2 per batch => 3 execute calls (one INSERT per chunk)
        assert mock_connector.cursor.execute.call_count == 3


class TestLoadCsv:

    def test_file_not_found(self, loader):
        result = loader.load_csv(Path("/nonexistent/file.csv"), "test_table")
        assert result.success is False
        assert "not found" in result.errors[0].lower()

    def test_csv_load_dispatches_through_inline_insert(self, loader, mock_connector, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Alice\n2,Bob\n")

        result = loader.load_csv(csv_file, "test_table")

        assert result.success is True
        mock_connector.cursor.execute.assert_called()
        insert_sql = mock_connector.cursor.execute.call_args[0][0]
        assert "INSERT INTO" in insert_sql
        assert "'Alice'" in insert_sql


class TestTruncateTable:

    def test_truncate_uses_three_part_name(self, loader, mock_connector):
        loader.truncate_table("dim_customers")
        mock_connector.execute_query.assert_called_with(
            "TRUNCATE TABLE main.ecommerce_dwh.dim_customers"
        )


class TestTableExists:

    def test_delegates_to_connector(self, loader, mock_connector):
        assert loader.table_exists("dim_customers") is True
        mock_connector.table_exists.assert_called_once_with(
            "dim_customers", schema="ecommerce_dwh"
        )


class TestGetRowCount:

    def test_returns_count(self, loader, mock_connector):
        mock_connector.execute_query.return_value = [(42,)]
        assert loader.get_row_count("dim_customers") == 42
