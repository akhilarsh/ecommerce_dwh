"""Tests for RedshiftConnector."""

import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_mock_redshift_connector():
    """
    Install a fake `redshift_connector` module so the real driver isn't required.

    If another test module already installed one, reuse it — otherwise the
    `import redshift_connector` line inside RedshiftConnector.connect picks up
    a different module than the one we patched, and our MagicMock writes go
    nowhere.
    """
    existing = sys.modules.get("redshift_connector")
    if existing is not None and isinstance(existing, types.ModuleType):
        if not hasattr(existing, "connect") or not isinstance(existing.connect, MagicMock):
            existing.connect = MagicMock()
        return existing

    mod = types.ModuleType("redshift_connector")
    mod.connect = MagicMock()
    sys.modules["redshift_connector"] = mod
    return mod


_RC_MOD = _install_mock_redshift_connector()


from src.connectors.redshift_connector import RedshiftConnector  # noqa: E402


PASSWORD_VARS = {
    "REDSHIFT_AUTH_METHOD": "password",
    "REDSHIFT_HOST": "mycluster.abc.us-east-1.redshift.amazonaws.com",
    "REDSHIFT_DATABASE": "ecommerce_db",
    "REDSHIFT_SCHEMA": "e_mart",
    "REDSHIFT_USER": "ecommerce_dwh",
    "REDSHIFT_PASSWORD": "secret",
}


@pytest.fixture
def env_password(monkeypatch):
    for k, v in PASSWORD_VARS.items():
        monkeypatch.setenv(k, v)
    for k in (
        "REDSHIFT_CLUSTER_IDENTIFIER",
        "REDSHIFT_WORKGROUP_NAME",
        "REDSHIFT_DB_USER",
        "AWS_REGION",
    ):
        monkeypatch.delenv(k, raising=False)
    return PASSWORD_VARS


@pytest.fixture
def env_iam_provisioned(monkeypatch):
    for k in PASSWORD_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "iam")
    monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
    monkeypatch.setenv("REDSHIFT_SCHEMA", "e_mart")
    monkeypatch.setenv("REDSHIFT_CLUSTER_IDENTIFIER", "mycluster")
    monkeypatch.setenv("REDSHIFT_DB_USER", "iam_user")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("REDSHIFT_WORKGROUP_NAME", raising=False)


@pytest.fixture
def env_iam_serverless(monkeypatch):
    for k in PASSWORD_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "iam")
    monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
    monkeypatch.setenv("REDSHIFT_SCHEMA", "e_mart")
    monkeypatch.setenv("REDSHIFT_WORKGROUP_NAME", "default-workgroup")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("REDSHIFT_CLUSTER_IDENTIFIER", raising=False)
    monkeypatch.delenv("REDSHIFT_DB_USER", raising=False)


class TestRedshiftConnectorValidation:

    def test_missing_database_raises(self, monkeypatch):
        for k in PASSWORD_VARS:
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(ValueError, match="database"):
            RedshiftConnector()

    def test_password_mode_missing_credentials_raises(self, monkeypatch):
        for k in PASSWORD_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "password")
        with pytest.raises(ValueError, match="password-auth"):
            RedshiftConnector()

    def test_iam_mode_requires_target(self, monkeypatch):
        for k in PASSWORD_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "iam")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        with pytest.raises(ValueError, match="CLUSTER_IDENTIFIER"):
            RedshiftConnector()

    def test_iam_provisioned_requires_db_user(self, monkeypatch):
        for k in PASSWORD_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "iam")
        monkeypatch.setenv("REDSHIFT_CLUSTER_IDENTIFIER", "mycluster")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("REDSHIFT_DB_USER", raising=False)
        with pytest.raises(ValueError, match="REDSHIFT_DB_USER"):
            RedshiftConnector()

    def test_iam_mode_requires_region(self, monkeypatch):
        for k in PASSWORD_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "iam")
        monkeypatch.setenv("REDSHIFT_CLUSTER_IDENTIFIER", "mycluster")
        monkeypatch.setenv("REDSHIFT_DB_USER", "u")
        monkeypatch.delenv("AWS_REGION", raising=False)
        with pytest.raises(ValueError, match="AWS_REGION"):
            RedshiftConnector()

    def test_unknown_auth_method_raises(self, monkeypatch):
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_AUTH_METHOD", "magic")
        with pytest.raises(ValueError, match="Unsupported"):
            RedshiftConnector()


class TestRedshiftConnectorEnvDefaults:

    def test_password_env_defaults(self, env_password):
        conn = RedshiftConnector()
        assert conn.host == PASSWORD_VARS["REDSHIFT_HOST"]
        assert conn.port == 5439
        assert conn.database == "ecommerce_db"
        assert conn.schema == "e_mart"
        assert conn.user == "ecommerce_dwh"
        assert conn.password == "secret"
        assert conn.auth_method == "password"
        assert conn.PLATFORM == "redshift"

    def test_default_schema_when_unset(self, monkeypatch):
        monkeypatch.setenv("REDSHIFT_DATABASE", "ecommerce_db")
        monkeypatch.setenv("REDSHIFT_HOST", "h")
        monkeypatch.setenv("REDSHIFT_USER", "u")
        monkeypatch.setenv("REDSHIFT_PASSWORD", "p")
        monkeypatch.delenv("REDSHIFT_SCHEMA", raising=False)
        conn = RedshiftConnector()
        assert conn.schema == "ecommerce_dwh"

    def test_explicit_constructor_overrides_env(self, env_password):
        conn = RedshiftConnector(
            host="other", database="other_db", user="u2", password="p2"
        )
        assert conn.host == "other"
        assert conn.database == "other_db"
        assert conn.user == "u2"
        assert conn.password == "p2"


class TestRedshiftConnectorConnect:

    def test_password_mode_invokes_driver(self, env_password):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        conn.connect()

        kwargs = _RC_MOD.connect.call_args.kwargs
        assert kwargs["host"] == PASSWORD_VARS["REDSHIFT_HOST"]
        assert kwargs["user"] == "ecommerce_dwh"
        assert kwargs["password"] == "secret"
        assert kwargs["database"] == "ecommerce_db"
        assert kwargs["port"] == 5439
        assert "iam" not in kwargs

    def test_iam_provisioned_invokes_driver(self, env_iam_provisioned):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        conn.connect()

        kwargs = _RC_MOD.connect.call_args.kwargs
        assert kwargs["iam"] is True
        assert kwargs["region"] == "us-east-1"
        assert kwargs["cluster_identifier"] == "mycluster"
        assert kwargs["db_user"] == "iam_user"
        assert "is_serverless" not in kwargs

    def test_iam_serverless_sets_workgroup(self, env_iam_serverless):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        conn.connect()

        kwargs = _RC_MOD.connect.call_args.kwargs
        assert kwargs["iam"] is True
        assert kwargs["is_serverless"] is True
        assert kwargs["workgroup_name"] == "default-workgroup"

    def test_connect_sets_search_path(self, env_password):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        conn.connect()

        # Cursor should have run a SET search_path statement.
        sql_calls = [c.args[0] for c in cursor.execute.call_args_list]
        assert any("SET search_path" in s and '"e_mart"' in s for s in sql_calls)

    def test_connect_rejects_unsafe_schema_identifier(self, env_password, monkeypatch):
        monkeypatch.setenv("REDSHIFT_SCHEMA", "e_mart;DROP TABLE foo")
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        with pytest.raises(ValueError, match="unsafe schema"):
            conn.connect()


class TestRedshiftConnectorOperations:

    def _connected(self, env_password):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        _RC_MOD.connect = MagicMock(return_value=connection)

        conn = RedshiftConnector()
        conn.connect()
        return conn, connection, cursor

    def test_execute_query_returns_rows_when_description_present(self, env_password):
        conn, _, cursor = self._connected(env_password)
        cursor.description = [("col",)]
        cursor.fetchall.return_value = [("a",), ("b",)]

        result = conn.execute_query("SELECT col FROM t")
        assert result == [("a",), ("b",)]

    def test_execute_query_returns_empty_for_ddl(self, env_password):
        conn, _, cursor = self._connected(env_password)
        cursor.description = None

        assert conn.execute_query("CREATE TABLE t (a INT)") == []

    def test_execute_query_without_connect_raises(self, env_password):
        # No connect call.
        conn = RedshiftConnector()
        with pytest.raises(RuntimeError, match="Not connected"):
            conn.execute_query("SELECT 1")

    def test_commit_calls_driver(self, env_password):
        conn, connection, _ = self._connected(env_password)
        conn.commit()
        connection.commit.assert_called_once()

    def test_rollback_calls_driver(self, env_password):
        conn, connection, _ = self._connected(env_password)
        conn.rollback()
        connection.rollback.assert_called_once()

    def test_table_exists_queries_information_schema(self, env_password):
        conn, _, cursor = self._connected(env_password)
        cursor.description = [("c",)]
        cursor.fetchall.return_value = [(1,)]

        assert conn.table_exists("dim_customers") is True
        # Last call should be the table-exists query with our schema + table.
        args, _ = cursor.execute.call_args
        assert "information_schema.tables" in args[0]
        assert args[1] == ("e_mart", "dim_customers")

    def test_context_manager_connects_and_closes(self, env_password):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        _RC_MOD.connect = MagicMock(return_value=connection)

        with RedshiftConnector() as conn:
            assert conn.connection is connection

        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_context_manager_rolls_back_on_exception(self, env_password):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        _RC_MOD.connect = MagicMock(return_value=connection)

        with pytest.raises(RuntimeError):
            with RedshiftConnector():
                raise RuntimeError("boom")

        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
