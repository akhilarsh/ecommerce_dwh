"""Tests for DatabricksConnector."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _install_mock_databricks_sql():
    """Install a fake `databricks.sql` module so `from databricks import sql` works."""
    fake_databricks = types.ModuleType("databricks")
    fake_sql = types.ModuleType("databricks.sql")
    fake_sql.connect = MagicMock()
    fake_databricks.sql = fake_sql
    sys.modules["databricks"] = fake_databricks
    sys.modules["databricks.sql"] = fake_sql
    return fake_sql


_install_mock_databricks_sql()


from src.connectors.databricks_connector import DatabricksConnector  # noqa: E402


REQUIRED_VARS = {
    "DATABRICKS_SERVER_HOSTNAME": "workspace.cloud.databricks.com",
    "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
    "DATABRICKS_ACCESS_TOKEN": "dapiXXXX",
    "DATABRICKS_CATALOG": "main",
    "DATABRICKS_SCHEMA": "ecommerce_dwh",
}


@pytest.fixture
def env_ok(monkeypatch):
    for k, v in REQUIRED_VARS.items():
        monkeypatch.setenv(k, v)
    return REQUIRED_VARS


class TestDatabricksConnectorInit:

    def test_missing_server_hostname_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(ValueError, match="Missing required Databricks parameters"):
            DatabricksConnector()

    def test_missing_http_path_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
        with pytest.raises(ValueError, match="http_path"):
            DatabricksConnector()

    def test_missing_access_token_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("DATABRICKS_CLIENT_ID", raising=False)
        monkeypatch.delenv("DATABRICKS_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
        monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
        with pytest.raises(ValueError, match="access_token"):
            DatabricksConnector()

    def test_oauth_m2m_satisfies_auth_requirement(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
        monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
        monkeypatch.setenv("DATABRICKS_CLIENT_ID", "client-id-uuid")
        monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "secret")
        # Should not raise — OAuth M2M creds satisfy auth requirement
        conn = DatabricksConnector()
        assert conn.auth_mode == "oauth_m2m"

    def test_oauth_missing_secret_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("DATABRICKS_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
        monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
        monkeypatch.setenv("DATABRICKS_CLIENT_ID", "client-id-uuid")
        # client_id alone (no secret, no PAT) -> falls back to PAT mode and fails
        with pytest.raises(ValueError, match="access_token"):
            DatabricksConnector()

    def test_missing_catalog_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
        monkeypatch.setenv("DATABRICKS_ACCESS_TOKEN", "tok")
        with pytest.raises(ValueError, match="catalog"):
            DatabricksConnector()

    def test_env_defaults(self, env_ok, monkeypatch):
        monkeypatch.delenv("DATABRICKS_CLIENT_ID", raising=False)
        monkeypatch.delenv("DATABRICKS_CLIENT_SECRET", raising=False)
        conn = DatabricksConnector()
        assert conn.server_hostname == REQUIRED_VARS["DATABRICKS_SERVER_HOSTNAME"]
        assert conn.http_path == REQUIRED_VARS["DATABRICKS_HTTP_PATH"]
        assert conn.access_token == REQUIRED_VARS["DATABRICKS_ACCESS_TOKEN"]
        assert conn.catalog == "main"
        assert conn.schema == "ecommerce_dwh"
        assert conn.database == "main"
        assert conn.auth_mode == "pat"
        assert conn.PLATFORM == "databricks"

    def test_default_schema_when_unset(self, monkeypatch):
        for k, v in REQUIRED_VARS.items():
            if k == "DATABRICKS_SCHEMA":
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        conn = DatabricksConnector()
        assert conn.schema == "ecommerce_dwh"

    def test_explicit_params_override_env(self, env_ok):
        conn = DatabricksConnector(
            server_hostname="other-host",
            http_path="/sql/1.0/warehouses/zzz",
            access_token="tok2",
            catalog="my_catalog",
            schema="my_schema",
        )
        assert conn.server_hostname == "other-host"
        assert conn.http_path == "/sql/1.0/warehouses/zzz"
        assert conn.access_token == "tok2"
        assert conn.catalog == "my_catalog"
        assert conn.schema == "my_schema"


class TestDatabricksConnectOperations:

    def test_connect_pat_passes_access_token(self, env_ok, monkeypatch):
        monkeypatch.delenv("DATABRICKS_CLIENT_ID", raising=False)
        monkeypatch.delenv("DATABRICKS_CLIENT_SECRET", raising=False)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("databricks.sql.connect", return_value=mock_conn) as mock_connect:
            conn = DatabricksConnector()
            conn.connect()

            assert mock_connect.call_count == 1
            kwargs = mock_connect.call_args.kwargs
            assert kwargs["server_hostname"] == REQUIRED_VARS["DATABRICKS_SERVER_HOSTNAME"]
            assert kwargs["http_path"] == REQUIRED_VARS["DATABRICKS_HTTP_PATH"]
            assert kwargs["access_token"] == REQUIRED_VARS["DATABRICKS_ACCESS_TOKEN"]
            assert "credentials_provider" not in kwargs

            use_stmts = [c.args[0] for c in mock_cursor.execute.call_args_list]
            assert any("USE CATALOG" in s for s in use_stmts)
            assert any("USE SCHEMA" in s for s in use_stmts)

    def test_connect_oauth_m2m_passes_credentials_provider(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "host")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
        monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
        monkeypatch.setenv("DATABRICKS_CLIENT_ID", "client-id-uuid")
        monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "secret")
        monkeypatch.delenv("DATABRICKS_ACCESS_TOKEN", raising=False)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Stub out databricks.sdk.core to avoid real OAuth
        fake_sdk = types.ModuleType("databricks.sdk")
        fake_sdk_core = types.ModuleType("databricks.sdk.core")
        fake_sdk_core.Config = MagicMock()
        fake_sdk_core.oauth_service_principal = MagicMock(return_value=lambda: {})
        sys.modules["databricks.sdk"] = fake_sdk
        sys.modules["databricks.sdk.core"] = fake_sdk_core

        with patch("databricks.sql.connect", return_value=mock_conn) as mock_connect:
            conn = DatabricksConnector()
            conn.connect()

            kwargs = mock_connect.call_args.kwargs
            assert "credentials_provider" in kwargs
            assert "access_token" not in kwargs
            assert callable(kwargs["credentials_provider"])

    def test_execute_query_returns_results(self, env_ok):
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = [(1,), (2,)]

        conn = DatabricksConnector()
        conn.cursor = mock_cursor

        result = conn.execute_query("SELECT 1")
        assert result == [(1,), (2,)]

    def test_execute_query_no_description_returns_empty(self, env_ok):
        mock_cursor = MagicMock()
        mock_cursor.description = None

        conn = DatabricksConnector()
        conn.cursor = mock_cursor

        result = conn.execute_query("CREATE TABLE t (id INT)")
        assert result == []

    def test_commit_is_noop(self, env_ok):
        conn = DatabricksConnector()
        # Should not raise even without an active connection (autocommit)
        conn.commit()

    def test_rollback_is_noop(self, env_ok):
        conn = DatabricksConnector()
        # Should not raise — Databricks SQL has no client-side transactions
        conn.rollback()

    def test_table_exists_true(self, env_ok):
        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(1,)]

        conn = DatabricksConnector()
        conn.cursor = mock_cursor

        assert conn.table_exists("dim_customers") is True

    def test_table_exists_false(self, env_ok):
        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(0,)]

        conn = DatabricksConnector()
        conn.cursor = mock_cursor

        assert conn.table_exists("nonexistent") is False

    def test_context_manager_connects_and_closes(self, env_ok):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("databricks.sql.connect", return_value=mock_conn):
            with DatabricksConnector() as conn:
                assert conn.connection is not None

            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_context_manager_closes_on_exception(self, env_ok):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("databricks.sql.connect", return_value=mock_conn):
            with pytest.raises(RuntimeError):
                with DatabricksConnector():
                    raise RuntimeError("boom")

            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()
