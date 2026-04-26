"""Tests for BigQuery DDL adapter type mapping and DDL generation."""

import pytest

from src.models.base_table import BaseTable, Column, ForeignKey
from src.sql_generator.bq_ddl_adapter import (
    _map_type,
    map_column_to_bq,
    generate_bq_create_table,
    generate_bq_drop_table,
    generate_bq_foreign_keys,
    generate_bq_create_schema,
)


class TestTypeMapping:

    def test_number_38_to_int64(self):
        # NUMBER(38,0) is the codebase's surrogate-key convention. We collapse
        # to INT64 (8-byte signed int, same width as Databricks BIGINT). For
        # actual numeric overflow, see test_number_large_precision_to_bignumeric.
        assert _map_type("NUMBER", None, 38, 0) == "INT64"

    def test_number_38_no_scale_to_int64(self):
        assert _map_type("NUMBER", None, 38, None) == "INT64"

    def test_number_small_precision_to_int64(self):
        assert _map_type("NUMBER", None, 1, 0) == "INT64"
        assert _map_type("NUMBER", None, 9, 0) == "INT64"
        assert _map_type("NUMBER", None, 18, 0) == "INT64"

    def test_number_large_precision_to_bignumeric(self):
        assert _map_type("NUMBER", None, 19, 0) == "BIGNUMERIC(19)"
        assert _map_type("NUMBER", None, 25, 0) == "BIGNUMERIC(25)"

    def test_number_with_scale_to_numeric(self):
        assert _map_type("NUMBER", None, 15, 2) == "NUMERIC(15,2)"
        assert _map_type("NUMBER", None, 10, 6) == "NUMERIC(10,6)"

    def test_varchar_any_length_to_string(self):
        assert _map_type("VARCHAR", 100, None, None) == "STRING"
        assert _map_type("VARCHAR", None, None, None) == "STRING"

    def test_timestamp_ntz_to_datetime(self):
        # BigQuery DATETIME has no timezone; matches Snowflake TIMESTAMP_NTZ.
        assert _map_type("TIMESTAMP_NTZ", None, None, None) == "DATETIME"

    def test_timestamp_passthrough(self):
        assert _map_type("TIMESTAMP", None, None, None) == "TIMESTAMP"

    def test_boolean_to_bool(self):
        assert _map_type("BOOLEAN", None, None, None) == "BOOL"

    def test_date_passthrough(self):
        assert _map_type("DATE", None, None, None) == "DATE"

    def test_time_passthrough(self):
        # BigQuery has a native TIME type.
        assert _map_type("TIME", None, None, None) == "TIME"

    def test_float_to_float64(self):
        assert _map_type("FLOAT", None, None, None) == "FLOAT64"

    def test_variant_to_json(self):
        # Native JSON, no parse_json wrapper at insert time.
        assert _map_type("VARIANT", None, None, None) == "JSON"

    def test_object_to_json(self):
        assert _map_type("OBJECT", None, None, None) == "JSON"

    def test_array_to_json(self):
        assert _map_type("ARRAY", None, None, None) == "JSON"

    def test_binary_to_bytes(self):
        assert _map_type("BINARY", None, None, None) == "BYTES"

    def test_geography_native(self):
        # BigQuery is the only target with first-class geo.
        assert _map_type("GEOGRAPHY", None, None, None) == "GEOGRAPHY"


class TestMapColumnToBq:

    def test_basic_column(self):
        col = Column(name="id", data_type="NUMBER", precision=18, scale=0, nullable=False)
        assert map_column_to_bq(col) == "id INT64 NOT NULL"

    def test_column_with_default(self):
        col = Column(name="active", data_type="BOOLEAN", default="FALSE")
        assert map_column_to_bq(col) == "active BOOL DEFAULT FALSE"

    def test_default_must_precede_not_null(self):
        # BigQuery rejects `BOOL NOT NULL DEFAULT FALSE` — DEFAULT must come
        # before NOT NULL. Caught the hard way during Phase 12 setup-tables.
        col = Column(
            name="is_featured", data_type="BOOLEAN",
            nullable=False, default="FALSE",
        )
        result = map_column_to_bq(col)
        assert result == "is_featured BOOL DEFAULT FALSE NOT NULL"
        # Position check: DEFAULT keyword index < NOT NULL index
        assert result.index("DEFAULT") < result.index("NOT NULL")

    def test_varchar_column_becomes_string(self):
        col = Column(name="name", data_type="VARCHAR", length=255, nullable=False)
        assert map_column_to_bq(col) == "name STRING NOT NULL"

    def test_comment_emits_options(self):
        col = Column(
            name="x",
            data_type="NUMBER",
            precision=18,
            scale=0,
            comment="Surrogate key",
        )
        result = map_column_to_bq(col)
        assert "x INT64" in result
        assert "OPTIONS (description = 'Surrogate key')" in result

    def test_json_column(self):
        col = Column(name="preferences", data_type="VARIANT", comment="User prefs")
        assert "preferences JSON" in map_column_to_bq(col)
        assert "OPTIONS (description = 'User prefs')" in map_column_to_bq(col)

    def test_geography_column(self):
        col = Column(name="home_location", data_type="GEOGRAPHY", comment="WKT POINT")
        result = map_column_to_bq(col)
        assert "home_location GEOGRAPHY" in result


class _FakeTable(BaseTable):
    table_name = "dim_test"
    comment = "Test dimension table"
    primary_key = ["test_key"]
    foreign_keys = []

    def define_columns(self):
        return [
            Column(name="test_key", data_type="NUMBER", precision=18, scale=0,
                   nullable=False, comment="Surrogate key"),
            Column(name="test_id", data_type="VARCHAR", length=50, nullable=False,
                   comment="Business key"),
            Column(name="amount", data_type="NUMBER", precision=15, scale=2,
                   comment="Dollar amount"),
            Column(name="preferences", data_type="VARIANT", comment="User prefs"),
            Column(name="home_location", data_type="GEOGRAPHY", comment="Geo point"),
            Column(name="raw_payload", data_type="BINARY", comment="Bytes payload"),
            Column(name="created_at", data_type="TIMESTAMP_NTZ", nullable=False),
            Column(name="is_active", data_type="BOOLEAN", default="TRUE"),
        ]


class _FakeTableWithFK(BaseTable):
    table_name = "fact_test"
    comment = "Test fact table"
    primary_key = ["fact_key"]
    foreign_keys = [
        ForeignKey(
            column="test_key",
            reference_table="dim_test",
            reference_column="test_key",
            constraint_name="fk_fact_test_test_key",
        ),
        ForeignKey(
            column="date_key",
            reference_table="dim_dates",
            reference_column="date_key",
            on_delete="CASCADE",
        ),
    ]

    def define_columns(self):
        return [
            Column(name="fact_key", data_type="NUMBER", precision=18, scale=0, nullable=False),
            Column(name="test_key", data_type="NUMBER", precision=18, scale=0, nullable=False),
            Column(name="date_key", data_type="NUMBER", precision=18, scale=0, nullable=False),
        ]


class TestGenerateBqCreateTable:

    def test_three_part_qualified_name_with_backticks(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert "CREATE TABLE IF NOT EXISTS `my-proj.mart.dim_test`" in sql

    def test_column_mappings_in_create(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert "test_key INT64 NOT NULL" in sql
        assert "test_id STRING NOT NULL" in sql
        assert "amount NUMERIC(15,2)" in sql
        assert "preferences JSON" in sql
        assert "home_location GEOGRAPHY" in sql
        assert "raw_payload BYTES" in sql
        assert "created_at DATETIME NOT NULL" in sql
        assert "is_active BOOL DEFAULT TRUE" in sql

    def test_primary_key_constraint_not_enforced(self):
        # BigQuery rejects `CONSTRAINT name PRIMARY KEY` inline; only the
        # unnamed `PRIMARY KEY (col) NOT ENFORCED` form is valid.
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert "PRIMARY KEY (test_key) NOT ENFORCED" in sql
        assert "CONSTRAINT pk_dim_test" not in sql

    def test_inline_table_options_description(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert "OPTIONS (description = 'Test dimension table')" in sql

    def test_inline_column_descriptions(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert "OPTIONS (description = 'Surrogate key')" in sql
        assert "OPTIONS (description = 'Business key')" in sql

    def test_comments_list_is_empty(self):
        # Comments are inline via OPTIONS; no separate COMMENT ON statements.
        _, comments = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        assert comments == []

    def test_no_other_platform_syntax(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "my-proj", "mart")
        # No Snowflake / Databricks artifacts
        assert "AUTOINCREMENT" not in sql
        assert "USING DELTA" not in sql
        assert "TBLPROPERTIES" not in sql
        assert "RELY" not in sql
        assert "COMMENT '" not in sql  # Databricks inline comment syntax
        assert "TIMESTAMP WITHOUT TIME ZONE" not in sql

    def test_single_quote_escaping(self):
        class _T(BaseTable):
            table_name = "dim_q"
            comment = "Table with 'single' quotes"
            primary_key = ["k"]
            foreign_keys = []

            def define_columns(self):
                return [
                    Column(
                        name="k", data_type="NUMBER", precision=18,
                        scale=0, comment="It's a key",
                    )
                ]

        sql, _ = generate_bq_create_table(_T(), "p", "d")
        assert "Table with ''single'' quotes" in sql
        assert "It''s a key" in sql
        assert "\\'" not in sql

    def test_hyphenated_project_id(self):
        sql, _ = generate_bq_create_table(_FakeTable(), "ecommerce-db", "e_mart")
        # Hyphens require backtick-quoted identifiers, which the adapter emits.
        assert "`ecommerce-db.e_mart.dim_test`" in sql


class TestGenerateBqDropTable:

    def test_drop_table_three_part_no_cascade(self):
        sql = generate_bq_drop_table(_FakeTable(), "my-proj", "mart")
        assert sql == "DROP TABLE IF EXISTS `my-proj.mart.dim_test`;"
        assert "CASCADE" not in sql


class TestGenerateBqForeignKeys:

    def test_fk_count_and_structure(self):
        fks = generate_bq_foreign_keys(_FakeTableWithFK(), "my-proj", "mart")
        assert len(fks) == 2

        first = fks[0]
        assert "ALTER TABLE `my-proj.mart.fact_test`" in first
        assert "fk_fact_test_test_key" in first
        assert "REFERENCES `my-proj.mart.dim_test`(test_key)" in first

    def test_fk_uses_not_enforced(self):
        fks = generate_bq_foreign_keys(_FakeTableWithFK(), "my-proj", "mart")
        for fk in fks:
            assert "NOT ENFORCED" in fk
            # BigQuery does not support RELY-style hints
            assert "RELY" not in fk

    def test_fk_omits_on_delete_cascade(self):
        # BigQuery FKs are not enforced and so do not support cascading actions.
        fks = generate_bq_foreign_keys(_FakeTableWithFK(), "my-proj", "mart")
        for fk in fks:
            assert "ON DELETE" not in fk
            assert "ON UPDATE" not in fk

    def test_fk_three_part_naming_with_backticks(self):
        fks = generate_bq_foreign_keys(_FakeTableWithFK(), "ecommerce-db", "e_mart")
        for fk in fks:
            assert "`ecommerce-db.e_mart." in fk

    def test_empty_fk_list(self):
        assert generate_bq_foreign_keys(_FakeTable(), "my-proj", "mart") == []


class TestGenerateBqCreateSchema:

    def test_create_schema_sql_with_location(self):
        sql = generate_bq_create_schema("ecommerce-db", "e_mart", location="US")
        assert "CREATE SCHEMA IF NOT EXISTS `ecommerce-db.e_mart`" in sql
        assert "OPTIONS (location = 'US')" in sql
        assert sql.endswith(";")

    def test_create_schema_sql_without_location(self):
        sql = generate_bq_create_schema("ecommerce-db", "e_mart")
        assert sql == "CREATE SCHEMA IF NOT EXISTS `ecommerce-db.e_mart`;"
