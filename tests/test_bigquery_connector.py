"""Tests for BigQueryConnector."""

import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_mock_google_cloud_bigquery():
    """
    Install fake `google.cloud.bigquery`, `google.cloud.exceptions`, and
    `google.oauth2.service_account` modules so the connector imports work
    without the real SDK being installed.
    """
    for name in (
        "google",
        "google.cloud",
        "google.cloud.bigquery",
        "google.cloud.exceptions",
        "google.oauth2",
        "google.oauth2.service_account",
    ):
        sys.modules.pop(name, None)

    google_pkg = types.ModuleType("google")
    google_pkg.__path__ = []
    sys.modules["google"] = google_pkg

    cloud_pkg = types.ModuleType("google.cloud")
    cloud_pkg.__path__ = []
    sys.modules["google.cloud"] = cloud_pkg
    google_pkg.cloud = cloud_pkg

    bq_mod = types.ModuleType("google.cloud.bigquery")
    bq_mod.Client = MagicMock()
    bq_mod.QueryJobConfig = MagicMock()
    bq_mod.LoadJobConfig = MagicMock()
    bq_mod.ScalarQueryParameter = MagicMock()
    bq_mod.SchemaField = MagicMock()
    bq_mod.WriteDisposition = types.SimpleNamespace(
        WRITE_APPEND="WRITE_APPEND",
        WRITE_TRUNCATE="WRITE_TRUNCATE",
        WRITE_EMPTY="WRITE_EMPTY",
    )
    bq_mod.SourceFormat = types.SimpleNamespace(
        NEWLINE_DELIMITED_JSON="NEWLINE_DELIMITED_JSON",
        PARQUET="PARQUET",
        CSV="CSV",
    )
    sys.modules["google.cloud.bigquery"] = bq_mod
    cloud_pkg.bigquery = bq_mod

    exc_mod = types.ModuleType("google.cloud.exceptions")

    class NotFound(Exception):
        pass

    exc_mod.NotFound = NotFound
    sys.modules["google.cloud.exceptions"] = exc_mod
    cloud_pkg.exceptions = exc_mod

    oauth2_pkg = types.ModuleType("google.oauth2")
    oauth2_pkg.__path__ = []
    sys.modules["google.oauth2"] = oauth2_pkg
    google_pkg.oauth2 = oauth2_pkg

    sa_mod = types.ModuleType("google.oauth2.service_account")
    sa_mod.Credentials = MagicMock()
    sa_mod.Credentials.from_service_account_file = MagicMock()
    sys.modules["google.oauth2.service_account"] = sa_mod
    oauth2_pkg.service_account = sa_mod

    return bq_mod


_BQ_MOD = _install_mock_google_cloud_bigquery()


# Import after mocks are installed.
from src.connectors.bigquery_connector import BigQueryConnector  # noqa: E402


REQUIRED_VARS = {
    "BIGQUERY_PROJECT": "ecommerce-db",
    "BIGQUERY_DATASET": "e_mart",
    "BIGQUERY_LOCATION": "US",
}


@pytest.fixture
def env_ok(monkeypatch):
    for k, v in REQUIRED_VARS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    return REQUIRED_VARS


class TestBigQueryConnectorInit:

    def test_missing_project_raises(self, monkeypatch):
        for k in REQUIRED_VARS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with pytest.raises(ValueError, match="project"):
            BigQueryConnector()

    def test_env_defaults(self, env_ok):
        conn = BigQueryConnector()
        assert conn.project == "ecommerce-db"
        assert conn.dataset == "e_mart"
        assert conn.location == "US"
        assert conn.credentials_path is None
        assert conn.database == "ecommerce-db"
        assert conn.schema == "e_mart"
        assert conn.PLATFORM == "bigquery"

    def test_default_dataset_when_unset(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_PROJECT", "p")
        monkeypatch.delenv("BIGQUERY_DATASET", raising=False)
        monkeypatch.delenv("BIGQUERY_LOCATION", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        conn = BigQueryConnector()
        assert conn.dataset == "ecommerce_dwh"
        assert conn.location == "US"

    def test_explicit_params_override_env(self, env_ok):
        conn = BigQueryConnector(
            project="other-proj",
            dataset="other_ds",
            location="EU",
            credentials_path="/path/to/key.json",
        )
        assert conn.project == "other-proj"
        assert conn.dataset == "other_ds"
        assert conn.location == "EU"
        assert conn.credentials_path == "/path/to/key.json"

    def test_credentials_path_picked_up_from_env(self, env_ok, monkeypatch):
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/some/key.json")
        conn = BigQueryConnector()
        assert conn.credentials_path == "/some/key.json"


class TestBigQueryConnectorOperations:

    def test_connect_uses_adc_when_no_credentials_path(self, env_ok):
        client_instance = MagicMock()
        _BQ_MOD.Client = MagicMock(return_value=client_instance)

        conn = BigQueryConnector()
        conn.connect()

        assert _BQ_MOD.Client.call_count == 1
        kwargs = _BQ_MOD.Client.call_args.kwargs
        assert kwargs["project"] == "ecommerce-db"
        assert "credentials" not in kwargs
        assert kwargs["location"] == "US"
        assert conn.client is client_instance

    def test_connect_uses_service_account_when_credentials_path_set(self, env_ok, monkeypatch):
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/some/key.json")

        sentinel_creds = MagicMock(name="creds")
        from google.oauth2 import service_account
        service_account.Credentials.from_service_account_file = MagicMock(
            return_value=sentinel_creds
        )

        client_instance = MagicMock()
        _BQ_MOD.Client = MagicMock(return_value=client_instance)

        conn = BigQueryConnector()
        conn.connect()

        kwargs = _BQ_MOD.Client.call_args.kwargs
        assert kwargs["credentials"] is sentinel_creds
        service_account.Credentials.from_service_account_file.assert_called_once_with(
            "/some/key.json"
        )

    def test_execute_query_returns_results(self, env_ok):
        from google.cloud import bigquery as bq

        # Mock the client's query() -> job -> result() pipeline.
        result_iter = MagicMock()
        result_iter.schema = [MagicMock()]
        # Each row exposes .values() returning a tuple.
        row1 = MagicMock(); row1.values.return_value = (1, "a")
        row2 = MagicMock(); row2.values.return_value = (2, "b")
        result_iter.__iter__ = MagicMock(return_value=iter([row1, row2]))

        job = MagicMock()
        job.result.return_value = result_iter

        client = MagicMock()
        client.query.return_value = job
        bq.Client = MagicMock(return_value=client)

        conn = BigQueryConnector()
        conn.connect()

        result = conn.execute_query("SELECT id, name FROM t")
        assert result == [(1, "a"), (2, "b")]
        client.query.assert_called_once()

    def test_execute_query_no_schema_returns_empty(self, env_ok):
        from google.cloud import bigquery as bq

        result_iter = MagicMock()
        result_iter.schema = None

        job = MagicMock()
        job.result.return_value = result_iter

        client = MagicMock()
        client.query.return_value = job
        bq.Client = MagicMock(return_value=client)

        conn = BigQueryConnector()
        conn.connect()

        result = conn.execute_query("CREATE TABLE t (id INT64)")
        assert result == []

    def test_execute_query_without_connect_raises(self, env_ok):
        conn = BigQueryConnector()
        with pytest.raises(RuntimeError, match="Not connected"):
            conn.execute_query("SELECT 1")

    def test_commit_is_noop(self, env_ok):
        conn = BigQueryConnector()
        # Should not raise even without an active client (autocommit).
        conn.commit()

    def test_rollback_is_noop(self, env_ok):
        conn = BigQueryConnector()
        # Should not raise — BigQuery has no client-side transactions.
        conn.rollback()

    def test_table_exists_true(self, env_ok):
        client = MagicMock()
        client.get_table.return_value = MagicMock()
        _BQ_MOD.Client = MagicMock(return_value=client)

        conn = BigQueryConnector()
        conn.connect()
        assert conn.table_exists("dim_customers") is True
        client.get_table.assert_called_once_with("ecommerce-db.e_mart.dim_customers")

    def test_table_exists_false(self, env_ok):
        from google.cloud.exceptions import NotFound

        client = MagicMock()
        client.get_table.side_effect = NotFound("missing")
        _BQ_MOD.Client = MagicMock(return_value=client)

        conn = BigQueryConnector()
        conn.connect()
        assert conn.table_exists("nonexistent") is False

    def test_get_current_database_returns_project(self, env_ok):
        conn = BigQueryConnector()
        assert conn.get_current_database() == "ecommerce-db"

    def test_get_current_schema_returns_dataset(self, env_ok):
        conn = BigQueryConnector()
        assert conn.get_current_schema() == "e_mart"

    def test_context_manager_connects_and_closes(self, env_ok):
        client = MagicMock()
        _BQ_MOD.Client = MagicMock(return_value=client)

        with BigQueryConnector() as conn:
            assert conn.client is client

        # close() called once on exit
        client.close.assert_called_once()

    def test_context_manager_closes_on_exception(self, env_ok):
        client = MagicMock()
        _BQ_MOD.Client = MagicMock(return_value=client)

        with pytest.raises(RuntimeError):
            with BigQueryConnector():
                raise RuntimeError("boom")

        client.close.assert_called_once()
