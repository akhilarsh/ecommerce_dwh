"""Tests for PostgresConnector."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from src.connectors.postgres_connector import PostgresConnector


class TestPostgresConnectorInit:

    def test_missing_user_raises(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_DATABASE", raising=False)
        with pytest.raises(ValueError, match="Missing required PostgreSQL parameters"):
            PostgresConnector(database="testdb")

    def test_missing_database_raises(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_DATABASE", raising=False)
        with pytest.raises(ValueError, match="Missing required PostgreSQL parameters"):
            PostgresConnector(user="testuser")

    def test_default_values(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "testuser")
        monkeypatch.setenv("POSTGRES_DATABASE", "testdb")
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)
        monkeypatch.delenv("POSTGRES_SCHEMA", raising=False)

        conn = PostgresConnector()
        assert conn.host == "localhost"
        assert conn.port == 5432
        assert conn.schema == "public"
        assert conn.PLATFORM == "postgres"

    def test_explicit_params_override_env(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "envuser")
        monkeypatch.setenv("POSTGRES_DATABASE", "envdb")

        conn = PostgresConnector(
            host="myhost", port=5433, user="myuser",
            password="secret", database="mydb", schema="myschema",
        )
        assert conn.host == "myhost"
        assert conn.port == 5433
        assert conn.user == "myuser"
        assert conn.database == "mydb"
        assert conn.schema == "myschema"


class TestPostgresConnectorOperations:

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_connect_sets_search_path(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        connector = PostgresConnector(schema="myschema")
        connector.connect()

        mock_psycopg2.connect.assert_called_once_with(
            host="localhost", port=5432, user="u", password=None, dbname="d",
        )
        mock_cursor.execute.assert_called_once_with("SET search_path TO myschema, public")

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_connect_skips_search_path_for_public(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        connector = PostgresConnector(schema="public")
        connector.connect()

        mock_cursor.execute.assert_not_called()

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_execute_query_returns_results(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = [(1,), (2,)]

        connector = PostgresConnector()
        connector.cursor = mock_cursor

        result = connector.execute_query("SELECT 1")
        assert result == [(1,), (2,)]

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_execute_query_no_description_returns_empty(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_cursor = MagicMock()
        mock_cursor.description = None

        connector = PostgresConnector()
        connector.cursor = mock_cursor

        result = connector.execute_query("CREATE TABLE t (id int)")
        assert result == []

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_table_exists_true(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(1,)]

        connector = PostgresConnector(schema="myschema")
        connector.cursor = mock_cursor

        assert connector.table_exists("dim_customers") is True

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_table_exists_false(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(0,)]

        connector = PostgresConnector(schema="myschema")
        connector.cursor = mock_cursor

        assert connector.table_exists("nonexistent") is False

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_context_manager_connects_and_closes(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        with PostgresConnector(schema="public") as conn:
            assert conn.connection is not None

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("src.connectors.postgres_connector.psycopg2")
    def test_context_manager_rollback_on_error(self, mock_psycopg2, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        with pytest.raises(RuntimeError):
            with PostgresConnector(schema="public") as conn:
                raise RuntimeError("boom")

        mock_conn.rollback.assert_called_once()
