"""Tests for Databricks DDL adapter type mapping and DDL generation."""

import pytest

from src.models.base_table import BaseTable, Column, ForeignKey
from src.sql_generator.dbx_ddl_adapter import (
    _map_type,
    map_column_to_dbx,
    generate_dbx_create_table,
    generate_dbx_drop_table,
    generate_dbx_foreign_keys,
    generate_dbx_create_schema,
)


class TestTypeMapping:

    def test_number_38_to_bigint(self):
        assert _map_type("NUMBER", None, 38, 0) == "BIGINT"

    def test_number_38_no_scale_to_bigint(self):
        assert _map_type("NUMBER", None, 38, None) == "BIGINT"

    def test_number_small_precision_to_int(self):
        assert _map_type("NUMBER", None, 1, 0) == "INT"
        assert _map_type("NUMBER", None, 5, 0) == "INT"
        assert _map_type("NUMBER", None, 9, 0) == "INT"

    def test_number_medium_precision_to_bigint(self):
        assert _map_type("NUMBER", None, 10, 0) == "BIGINT"
        assert _map_type("NUMBER", None, 18, 0) == "BIGINT"

    def test_number_large_precision_to_decimal(self):
        assert _map_type("NUMBER", None, 25, 0) == "DECIMAL(25,0)"

    def test_number_with_scale_to_decimal(self):
        assert _map_type("NUMBER", None, 15, 2) == "DECIMAL(15,2)"
        assert _map_type("NUMBER", None, 10, 6) == "DECIMAL(10,6)"

    def test_varchar_any_length_to_string(self):
        assert _map_type("VARCHAR", 100, None, None) == "STRING"
        assert _map_type("VARCHAR", None, None, None) == "STRING"

    def test_timestamp_ntz_passthrough(self):
        assert _map_type("TIMESTAMP_NTZ", None, None, None) == "TIMESTAMP_NTZ"

    def test_timestamp_passthrough(self):
        assert _map_type("TIMESTAMP", None, None, None) == "TIMESTAMP"

    def test_boolean_passthrough(self):
        assert _map_type("BOOLEAN", None, None, None) == "BOOLEAN"

    def test_date_passthrough(self):
        assert _map_type("DATE", None, None, None) == "DATE"

    def test_time_to_string(self):
        # Databricks has no TIME type
        assert _map_type("TIME", None, None, None) == "STRING"

    def test_float_to_double(self):
        assert _map_type("FLOAT", None, None, None) == "DOUBLE"

    def test_variant_native(self):
        assert _map_type("VARIANT", None, None, None) == "VARIANT"

    def test_object_to_variant(self):
        assert _map_type("OBJECT", None, None, None) == "VARIANT"

    def test_array_to_variant(self):
        assert _map_type("ARRAY", None, None, None) == "VARIANT"

    def test_binary_passthrough(self):
        assert _map_type("BINARY", None, None, None) == "BINARY"

    def test_geography_to_string(self):
        assert _map_type("GEOGRAPHY", None, None, None) == "STRING"


class TestMapColumnToDbx:

    def test_basic_column(self):
        col = Column(name="id", data_type="NUMBER", precision=38, scale=0, nullable=False)
        assert map_column_to_dbx(col) == "id BIGINT NOT NULL"

    def test_column_with_default(self):
        col = Column(name="active", data_type="BOOLEAN", default="FALSE")
        assert map_column_to_dbx(col) == "active BOOLEAN DEFAULT FALSE"

    def test_varchar_column_becomes_string(self):
        col = Column(name="name", data_type="VARCHAR", length=255, nullable=False)
        assert map_column_to_dbx(col) == "name STRING NOT NULL"

    def test_comment_is_inline(self):
        col = Column(
            name="x",
            data_type="NUMBER",
            precision=38,
            scale=0,
            comment="Surrogate key",
        )
        result = map_column_to_dbx(col)
        assert result == "x BIGINT COMMENT 'Surrogate key'"

    def test_variant_column(self):
        col = Column(name="preferences", data_type="VARIANT", comment="User prefs")
        assert map_column_to_dbx(col) == "preferences VARIANT COMMENT 'User prefs'"


class _FakeTable(BaseTable):
    table_name = "dim_test"
    comment = "Test dimension table"
    primary_key = ["test_key"]
    foreign_keys = []

    def define_columns(self):
        return [
            Column(name="test_key", data_type="NUMBER", precision=38, scale=0,
                   nullable=False, comment="Surrogate key"),
            Column(name="test_id", data_type="VARCHAR", length=50, nullable=False,
                   comment="Business key"),
            Column(name="amount", data_type="NUMBER", precision=15, scale=2,
                   comment="Dollar amount"),
            Column(name="preferences", data_type="VARIANT", comment="User prefs"),
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
            Column(name="fact_key", data_type="NUMBER", precision=38, scale=0, nullable=False),
            Column(name="test_key", data_type="NUMBER", precision=38, scale=0, nullable=False),
            Column(name="date_key", data_type="NUMBER", precision=38, scale=0, nullable=False),
        ]


class TestGenerateDbxCreateTable:

    def test_three_part_qualified_name(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "CREATE TABLE IF NOT EXISTS main.ecommerce_dwh.dim_test" in sql

    def test_column_mappings_in_create(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "test_key BIGINT NOT NULL" in sql
        assert "test_id STRING NOT NULL" in sql
        assert "amount DECIMAL(15,2)" in sql
        assert "preferences VARIANT" in sql
        assert "created_at TIMESTAMP_NTZ NOT NULL" in sql
        assert "is_active BOOLEAN DEFAULT TRUE" in sql

    def test_primary_key_constraint_with_rely(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "CONSTRAINT pk_dim_test PRIMARY KEY (test_key) RELY" in sql

    def test_using_delta_clause(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "USING DELTA" in sql

    def test_tblproperties_enables_column_defaults(self):
        # Required to allow DEFAULT clauses on Delta tables
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "TBLPROPERTIES" in sql
        assert "delta.feature.allowColumnDefaults" in sql
        assert "'supported'" in sql

    def test_inline_table_comment(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "COMMENT 'Test dimension table'" in sql

    def test_inline_column_comments(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "COMMENT 'Surrogate key'" in sql
        assert "COMMENT 'Business key'" in sql

    def test_comments_list_is_empty(self):
        # Comments are inline on Databricks; no separate COMMENT ON statements.
        _, comments = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert comments == []

    def test_no_snowflake_syntax(self):
        sql, _ = generate_dbx_create_table(_FakeTable(), "main", "ecommerce_dwh")
        assert "AUTOINCREMENT" not in sql
        assert "CLUSTER BY" not in sql
        assert "COMMENT =" not in sql  # Snowflake's table comment syntax
        assert "NUMBER(" not in sql
        assert "TIMESTAMP WITHOUT TIME ZONE" not in sql

    def test_single_quote_escaping(self):
        class _T(BaseTable):
            table_name = "dim_q"
            comment = "Table with 'single' quotes"
            primary_key = ["k"]
            foreign_keys = []

            def define_columns(self):
                return [Column(name="k", data_type="NUMBER", precision=38,
                               scale=0, comment="It's a key")]

        sql, _ = generate_dbx_create_table(_T(), "main", "s")
        assert "Table with ''single'' quotes" in sql
        assert "It''s a key" in sql
        assert "\\'" not in sql


class TestGenerateDbxDropTable:

    def test_drop_table_three_part_no_cascade(self):
        sql = generate_dbx_drop_table(_FakeTable(), "main", "ecommerce_dwh")
        assert sql == "DROP TABLE IF EXISTS main.ecommerce_dwh.dim_test;"
        assert "CASCADE" not in sql


class TestGenerateDbxForeignKeys:

    def test_fk_count_and_structure(self):
        fks = generate_dbx_foreign_keys(_FakeTableWithFK(), "main", "ecommerce_dwh")
        assert len(fks) == 2

        first = fks[0]
        assert "ALTER TABLE main.ecommerce_dwh.fact_test" in first
        assert "fk_fact_test_test_key" in first
        assert "REFERENCES main.ecommerce_dwh.dim_test(test_key)" in first

    def test_fk_uses_not_enforced_rely(self):
        fks = generate_dbx_foreign_keys(_FakeTableWithFK(), "main", "ecommerce_dwh")
        for fk in fks:
            assert "NOT ENFORCED RELY" in fk

    def test_fk_omits_on_delete_cascade(self):
        # Databricks Delta FKs do not support cascading actions.
        fks = generate_dbx_foreign_keys(_FakeTableWithFK(), "main", "ecommerce_dwh")
        for fk in fks:
            assert "ON DELETE" not in fk
            assert "ON UPDATE" not in fk

    def test_fk_three_part_naming(self):
        fks = generate_dbx_foreign_keys(_FakeTableWithFK(), "my_cat", "my_schema")
        for fk in fks:
            assert "my_cat.my_schema." in fk

    def test_empty_fk_list(self):
        assert generate_dbx_foreign_keys(_FakeTable(), "main", "s") == []


class TestGenerateDbxCreateSchema:

    def test_create_schema_sql(self):
        sql = generate_dbx_create_schema("main", "ecommerce_dwh")
        assert sql == "CREATE SCHEMA IF NOT EXISTS main.ecommerce_dwh;"
