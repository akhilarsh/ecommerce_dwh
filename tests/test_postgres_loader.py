"""Tests for PostgresLoader."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from src.data_loaders.base_loader import LoaderConfig
from src.data_loaders.postgres_loader import PostgresLoader


@pytest.fixture
def mock_connector():
    conn = MagicMock()
    conn.PLATFORM = "postgres"
    conn.database = "testdb"
    conn.schema = "testschema"
    conn.cursor = MagicMock()
    conn.connection = MagicMock()
    conn.execute_query = MagicMock(return_value=[(100,)])
    conn.table_exists = MagicMock(return_value=True)
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    return conn


@pytest.fixture
def loader(mock_connector):
    config = LoaderConfig(
        batch_size=5000,
        truncate_before_load=False,
        validate_after_load=False,
    )
    return PostgresLoader(mock_connector, config)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "amount": [10.5, 20.0, 30.75],
    })


class TestPostgresLoaderInit:

    def test_platform_name(self, loader):
        assert loader.platform_name == "postgres"

    def test_inherits_connector_schema(self, mock_connector):
        loader = PostgresLoader(mock_connector)
        assert loader.config.schema == "testschema"

    def test_inherits_connector_database(self, mock_connector):
        loader = PostgresLoader(mock_connector)
        assert loader.config.database == "testdb"


class TestLoadDataframe:

    @patch("src.data_loaders.postgres_loader.psycopg2.extras.execute_values")
    def test_small_df_uses_execute_values(self, mock_exec_values, loader, sample_df):
        result = loader.load_dataframe(sample_df, "test_table")

        assert result.success is True
        assert result.rows_loaded == 3
        mock_exec_values.assert_called_once()
        loader.connector.commit.assert_called()

    @patch("src.data_loaders.postgres_loader.psycopg2.extras.execute_values")
    def test_nan_converted_to_none(self, mock_exec_values, loader):
        df = pd.DataFrame({"id": [1, 2], "val": [10.0, float("nan")]})
        loader.load_dataframe(df, "test_table")

        call_args = mock_exec_values.call_args
        data = call_args[0][2]
        assert data[1][1] is None

    def test_empty_df_returns_validation_error(self, loader):
        df = pd.DataFrame()
        result = loader.load_dataframe(df, "test_table")
        assert result.success is False
        assert len(result.errors) > 0

    @patch("src.data_loaders.postgres_loader.psycopg2.extras.execute_values")
    def test_truncate_before_load(self, mock_exec_values, mock_connector, sample_df):
        config = LoaderConfig(truncate_before_load=True, validate_after_load=False)
        loader = PostgresLoader(mock_connector, config)
        loader.load_dataframe(sample_df, "test_table")

        truncate_calls = [
            c for c in mock_connector.execute_query.call_args_list
            if "TRUNCATE" in str(c)
        ]
        assert len(truncate_calls) > 0


class TestLoadCsv:

    def test_file_not_found(self, loader):
        result = loader.load_csv(Path("/nonexistent/file.csv"), "test_table")
        assert result.success is False
        assert "not found" in result.errors[0].lower()

    def test_csv_load_uses_copy_expert(self, loader, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Alice\n2,Bob\n")

        loader.load_csv(csv_file, "test_table")

        loader.connector.cursor.copy_expert.assert_called_once()
        call_args = loader.connector.cursor.copy_expert.call_args[0]
        assert "COPY" in call_args[0]
        assert "FROM STDIN" in call_args[0]


class TestTruncateTable:

    def test_truncate_cascade(self, loader, mock_connector):
        loader.truncate_table("dim_customers")

        mock_connector.execute_query.assert_called_with(
            "TRUNCATE TABLE testschema.dim_customers CASCADE"
        )
        mock_connector.commit.assert_called()


class TestTableExists:

    def test_delegates_to_connector(self, loader, mock_connector):
        result = loader.table_exists("dim_customers")
        mock_connector.table_exists.assert_called_once_with("dim_customers", schema="testschema")
        assert result is True


class TestGetRowCount:

    def test_returns_count(self, loader, mock_connector):
        mock_connector.execute_query.return_value = [(42,)]
        assert loader.get_row_count("dim_customers") == 42
