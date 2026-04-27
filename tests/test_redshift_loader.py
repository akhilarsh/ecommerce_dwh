"""Tests for RedshiftLoader."""

import base64
import gzip
import json
import sys
import types
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _install_mock_redshift_connector():
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
# boto3 is intentionally NOT mocked: snowflake-connector accesses
# botocore.config.Config at module level, and `import boto3` is what loads
# that submodule. Mocking boto3 broke the import chain. Tests stub the S3
# client at the loader level via `loader._s3_client = mock_s3` instead.


from src.connectors.redshift_connector import RedshiftConnector  # noqa: E402
from src.data_loaders.redshift_loader import (  # noqa: E402
    RedshiftLoader,
    _to_json_value,
    _to_insert_value,
)
from src.data_loaders.base_loader import LoaderConfig, LoadMethod  # noqa: E402


PASSWORD_VARS = {
    "REDSHIFT_AUTH_METHOD": "password",
    "REDSHIFT_HOST": "h",
    "REDSHIFT_DATABASE": "ecommerce_db",
    "REDSHIFT_SCHEMA": "e_mart",
    "REDSHIFT_USER": "u",
    "REDSHIFT_PASSWORD": "p",
}


@pytest.fixture
def env_password(monkeypatch):
    for k, v in PASSWORD_VARS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("REDSHIFT_S3_STAGING_BUCKET", raising=False)
    monkeypatch.delenv("REDSHIFT_COPY_IAM_ROLE", raising=False)
    monkeypatch.delenv("REDSHIFT_LOADER_MODE", raising=False)
    monkeypatch.delenv("REDSHIFT_COPY_THRESHOLD", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    return PASSWORD_VARS


@pytest.fixture
def env_with_s3(env_password, monkeypatch):
    monkeypatch.setenv("REDSHIFT_S3_STAGING_BUCKET", "stagebucket")
    monkeypatch.setenv("REDSHIFT_COPY_IAM_ROLE", "arn:aws:iam::1:role/r")
    return env_password


def _build_connected_connector():
    connection = MagicMock()
    cursor = MagicMock()
    cursor.description = None
    connection.cursor.return_value = cursor
    _RC_MOD.connect = MagicMock(return_value=connection)

    conn = RedshiftConnector()
    conn.connect()
    return conn, cursor


class TestRedshiftLoaderBasics:

    def test_platform_name(self, env_password):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader.platform_name == "redshift"

    def test_inherits_database_and_schema(self, env_password):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader.config.database == "ecommerce_db"
        assert loader.config.schema == "e_mart"

    def test_copy_unavailable_without_bucket(self, env_password):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader.copy_available is False

    def test_copy_available_with_bucket_and_role(self, env_with_s3):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader.copy_available is True


class TestStrategySelection:

    def test_small_load_uses_insert(self, env_with_s3, monkeypatch):
        # Threshold default is 5000; 100 rows must use INSERT regardless of S3.
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader._select_strategy(100) == "insert"

    def test_large_load_uses_copy_when_s3_set(self, env_with_s3):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader._select_strategy(10000) == "copy"

    def test_large_load_falls_back_to_insert_without_s3(self, env_password):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        # Even at huge sizes, INSERT is the only option without staging.
        assert loader._select_strategy(1_000_000) == "insert"

    def test_forced_insert_mode(self, env_with_s3, monkeypatch):
        monkeypatch.setenv("REDSHIFT_LOADER_MODE", "insert")
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        assert loader._select_strategy(1_000_000) == "insert"

    def test_forced_copy_mode_without_bucket_raises(self, env_password, monkeypatch):
        monkeypatch.setenv("REDSHIFT_LOADER_MODE", "copy")
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        with pytest.raises(RuntimeError, match="REDSHIFT_S3_STAGING_BUCKET"):
            loader._select_strategy(10)


class TestInsertPath:

    def test_load_dataframe_uses_multi_row_insert(self, env_password):
        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))

        # Avoid information_schema introspection — patch the cache.
        loader._schema_cache["dim_t"] = [
            ("id", "BIGINT"),
            ("name", "VARCHAR"),
        ]

        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        result = loader.load_dataframe(df, "dim_t")

        assert result.success is True
        assert result.rows_loaded == 3
        assert result.method == LoadMethod.DATAFRAME
        # INSERT path uses execute (single multi-row statement), NOT
        # executemany — that's the whole point of the rewrite.
        insert_call = next(
            (c for c in cursor.execute.call_args_list
             if c.args[0].startswith("INSERT INTO e_mart.dim_t")),
            None,
        )
        assert insert_call is not None, "no INSERT statement issued"
        sql_used = insert_call.args[0]
        # Three rows -> three parenthesized VALUES groups.
        assert sql_used.count("(%s, %s)") == 3
        # Flat parameter list: 3 rows * 2 cols = 6 values.
        assert len(insert_call.args[1]) == 6

    def test_super_column_uses_json_parse_wrapper(self, env_password):
        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))
        loader._schema_cache["dim_t"] = [
            ("id", "BIGINT"),
            ("preferences", "SUPER"),
        ]

        df = pd.DataFrame({
            "id": [1],
            "preferences": ['{"theme": "dark"}'],
        })
        loader.load_dataframe(df, "dim_t")

        insert_call = next(
            (c for c in cursor.execute.call_args_list
             if c.args[0].startswith("INSERT INTO")), None,
        )
        assert insert_call is not None
        assert "JSON_PARSE(%s)" in insert_call.args[0]

    def test_geography_column_uses_st_geogfromtext_wrapper(self, env_password):
        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))
        loader._schema_cache["dim_t"] = [
            ("id", "BIGINT"),
            ("home_location", "GEOGRAPHY"),
        ]

        df = pd.DataFrame({
            "id": [1],
            "home_location": ["POINT(-116.5 30.4)"],
        })
        loader.load_dataframe(df, "dim_t")

        insert_call = next(
            (c for c in cursor.execute.call_args_list
             if c.args[0].startswith("INSERT INTO")), None,
        )
        assert insert_call is not None
        assert "ST_GeogFromText(%s)" in insert_call.args[0]

    def test_truncate_before_load(self, env_password):
        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(
            conn, LoaderConfig(truncate_before_load=True, validate_after_load=False)
        )
        loader._schema_cache["dim_t"] = [("id", "BIGINT")]

        df = pd.DataFrame({"id": [1]})
        loader.load_dataframe(df, "dim_t")

        # cursor.execute should have run a TRUNCATE statement somewhere.
        executed = [c.args[0] for c in cursor.execute.call_args_list]
        assert any("TRUNCATE TABLE e_mart.dim_t" in s for s in executed)

    def test_empty_dataframe_returns_validation_error(self, env_password):
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        result = loader.load_dataframe(pd.DataFrame(), "dim_t")
        assert result.success is False
        assert any("empty" in e.lower() for e in result.errors)


class TestCopyPath:

    def test_copy_uploads_and_runs_copy_sql(self, env_with_s3, monkeypatch):
        # Force copy mode regardless of size.
        monkeypatch.setenv("REDSHIFT_LOADER_MODE", "copy")

        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))
        loader._schema_cache["fact_t"] = [("id", "BIGINT"), ("amt", "NUMERIC")]

        s3 = MagicMock()
        loader._s3_client = s3

        df = pd.DataFrame({"id": [1, 2], "amt": [1.0, 2.5]})
        result = loader.load_dataframe(df, "fact_t")

        assert result.success is True
        assert result.method == LoadMethod.STAGED

        # put_object invoked with our bucket and a database/schema/table key.
        put_kwargs = s3.put_object.call_args.kwargs
        assert put_kwargs["Bucket"] == "stagebucket"
        assert put_kwargs["Key"].startswith("ecommerce_db/e_mart/fact_t/")
        assert put_kwargs["Key"].endswith(".json.gz")

        # COPY SQL was issued.
        copy_sql = next(
            (c.args[0] for c in cursor.execute.call_args_list if c.args[0].startswith("COPY")),
            None,
        )
        assert copy_sql is not None
        assert "FROM 's3://stagebucket/ecommerce_db/e_mart/fact_t/" in copy_sql
        assert "IAM_ROLE 'arn:aws:iam::1:role/r'" in copy_sql
        assert "FORMAT AS JSON 'auto'" in copy_sql
        assert "GZIP" in copy_sql
        assert "REGION 'us-east-1'" in copy_sql

    def test_copy_deletes_object_on_success(self, env_with_s3, monkeypatch):
        monkeypatch.setenv("REDSHIFT_LOADER_MODE", "copy")

        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))
        loader._schema_cache["fact_t"] = [("id", "BIGINT")]

        s3 = MagicMock()
        loader._s3_client = s3

        df = pd.DataFrame({"id": [1]})
        loader.load_dataframe(df, "fact_t")

        s3.delete_object.assert_called_once()
        del_kwargs = s3.delete_object.call_args.kwargs
        assert del_kwargs["Bucket"] == "stagebucket"

    def test_copy_keeps_object_on_failure(self, env_with_s3, monkeypatch):
        monkeypatch.setenv("REDSHIFT_LOADER_MODE", "copy")

        conn, cursor = _build_connected_connector()
        loader = RedshiftLoader(conn, LoaderConfig(validate_after_load=False))
        loader._schema_cache["fact_t"] = [("id", "BIGINT")]

        s3 = MagicMock()
        loader._s3_client = s3

        # Make the cursor raise on COPY by failing on any execute call that
        # starts with "COPY".
        original_execute = cursor.execute
        def execute_side_effect(sql, *args, **kwargs):
            if sql.startswith("COPY"):
                raise RuntimeError("permission denied on bucket")
            return original_execute(sql, *args, **kwargs)
        cursor.execute.side_effect = execute_side_effect

        df = pd.DataFrame({"id": [1]})
        result = loader.load_dataframe(df, "fact_t")

        assert result.success is False
        # Must NOT have called delete_object after failure.
        s3.delete_object.assert_not_called()


class TestSerialization:

    def test_super_dict_passes_through(self):
        assert _to_json_value({"a": 1}, "SUPER") == {"a": 1}

    def test_super_string_is_parsed(self):
        assert _to_json_value('{"a": 1}', "SUPER") == {"a": 1}

    def test_super_invalid_json_falls_back(self):
        assert _to_json_value("not json", "SUPER") == "not json"

    def test_numeric_stringified(self):
        from decimal import Decimal
        assert _to_json_value(Decimal("12.34"), "NUMERIC(15,2)") == "12.34"

    def test_varbyte_base64_to_hex(self):
        b64 = base64.b64encode(b"hello").decode("ascii")
        assert _to_json_value(b64, "VARBYTE") == b"hello".hex()

    def test_geography_passthrough(self):
        assert _to_json_value("POINT(1 2)", "GEOGRAPHY") == "POINT(1 2)"

    def test_null_collapses_to_none(self):
        import math
        assert _to_json_value(None, "VARCHAR") is None
        assert _to_json_value(math.nan, "NUMERIC") is None

    def test_insert_value_super_serializes_dict(self):
        # JSON_PARSE wrapper takes a JSON string.
        assert _to_insert_value({"a": 1}, "SUPER") == '{"a": 1}'

    def test_insert_value_super_passes_string_through(self):
        assert _to_insert_value('{"a": 1}', "SUPER") == '{"a": 1}'

    def test_insert_value_varbyte_decodes_base64(self):
        b64 = base64.b64encode(b"hi").decode("ascii")
        assert _to_insert_value(b64, "VARBYTE") == b"hi"


class TestRowCount:

    def test_get_row_count(self, env_password):
        conn, cursor = _build_connected_connector()
        cursor.description = [("count",)]
        cursor.fetchall.return_value = [(42,)]

        loader = RedshiftLoader(conn)
        assert loader.get_row_count("dim_t") == 42

    def test_table_exists_delegates_to_connector(self, env_password):
        conn, cursor = _build_connected_connector()
        cursor.description = [("c",)]
        cursor.fetchall.return_value = [(1,)]

        loader = RedshiftLoader(conn)
        assert loader.table_exists("dim_t") is True


class TestCsvLoading:

    def test_load_csv_missing_file_returns_error(self, env_password):
        from pathlib import Path
        conn, _ = _build_connected_connector()
        loader = RedshiftLoader(conn)
        result = loader.load_csv(Path("/nonexistent/file.csv"), "dim_t")
        assert result.success is False
        assert any("not found" in e.lower() for e in result.errors)
