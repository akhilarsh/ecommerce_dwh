"""Tests for PostgreSQL DDL adapter type mapping and DDL generation."""

import pytest

from src.models.base_table import BaseTable, Column, ForeignKey
from src.sql_generator.pg_ddl_adapter import (
    map_column_to_pg,
    _map_type,
    generate_pg_create_table,
    generate_pg_drop_table,
    generate_pg_foreign_keys,
)


class TestTypeMapping:

    def test_number_38_to_bigint(self):
        assert _map_type("NUMBER", None, 38, 0) == "BIGINT"

    def test_number_38_no_scale_to_bigint(self):
        assert _map_type("NUMBER", None, 38, None) == "BIGINT"

    def test_number_small_precision_to_integer(self):
        assert _map_type("NUMBER", None, 1, 0) == "INTEGER"
        assert _map_type("NUMBER", None, 5, 0) == "INTEGER"
        assert _map_type("NUMBER", None, 9, 0) == "INTEGER"

    def test_number_medium_precision_to_bigint(self):
        assert _map_type("NUMBER", None, 10, 0) == "BIGINT"
        assert _map_type("NUMBER", None, 18, 0) == "BIGINT"

    def test_number_with_scale_to_numeric(self):
        assert _map_type("NUMBER", None, 15, 2) == "NUMERIC(15,2)"
        assert _map_type("NUMBER", None, 10, 6) == "NUMERIC(10,6)"
        assert _map_type("NUMBER", None, 18, 4) == "NUMERIC(18,4)"

    def test_varchar_with_length(self):
        assert _map_type("VARCHAR", 100, None, None) == "VARCHAR(100)"

    def test_varchar_without_length(self):
        assert _map_type("VARCHAR", None, None, None) == "VARCHAR"

    def test_timestamp_ntz(self):
        assert _map_type("TIMESTAMP_NTZ", None, None, None) == "TIMESTAMP WITHOUT TIME ZONE"

    def test_boolean_passthrough(self):
        assert _map_type("BOOLEAN", None, None, None) == "BOOLEAN"

    def test_date_passthrough(self):
        assert _map_type("DATE", None, None, None) == "DATE"

    def test_time_passthrough(self):
        assert _map_type("TIME", None, None, None) == "TIME"

    def test_float_to_double_precision(self):
        assert _map_type("FLOAT", None, None, None) == "DOUBLE PRECISION"


class TestMapColumnToPg:

    def test_basic_column(self):
        col = Column(name="id", data_type="NUMBER", precision=38, scale=0, nullable=False)
        result = map_column_to_pg(col)
        assert result == "id BIGINT NOT NULL"

    def test_column_with_default(self):
        col = Column(name="active", data_type="BOOLEAN", default="FALSE", nullable=True)
        result = map_column_to_pg(col)
        assert result == "active BOOLEAN DEFAULT FALSE"

    def test_varchar_column(self):
        col = Column(name="name", data_type="VARCHAR", length=255, nullable=False)
        result = map_column_to_pg(col)
        assert result == "name VARCHAR(255) NOT NULL"

    def test_comment_is_not_included(self):
        col = Column(name="x", data_type="NUMBER", precision=38, scale=0, comment="Surrogate key")
        result = map_column_to_pg(col)
        assert "COMMENT" not in result
        assert "Surrogate" not in result


class _FakeTable(BaseTable):
    table_name = "dim_test"
    schema_name = "test_schema"
    comment = "Test dimension table"
    primary_key = ["test_key"]
    foreign_keys = []

    def define_columns(self):
        return [
            Column(name="test_key", data_type="NUMBER", precision=38, scale=0, nullable=False, comment="Surrogate key"),
            Column(name="test_id", data_type="VARCHAR", length=50, nullable=False, comment="Business key"),
            Column(name="amount", data_type="NUMBER", precision=15, scale=2, comment="Dollar amount"),
            Column(name="created_at", data_type="TIMESTAMP_NTZ", nullable=False),
            Column(name="is_active", data_type="BOOLEAN", default="TRUE"),
        ]


class _FakeTableWithFK(BaseTable):
    table_name = "fact_test"
    schema_name = "test_schema"
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


class TestGeneratePgCreateTable:

    def test_create_table_structure(self):
        table = _FakeTable()
        sql, comments = generate_pg_create_table(table, "ecommerce_dwh")

        assert "CREATE TABLE IF NOT EXISTS ecommerce_dwh.dim_test" in sql
        assert "test_key BIGINT NOT NULL" in sql
        assert "test_id VARCHAR(50) NOT NULL" in sql
        assert "amount NUMERIC(15,2)" in sql
        assert "created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL" in sql
        assert "is_active BOOLEAN DEFAULT TRUE" in sql
        assert "PRIMARY KEY (test_key)" in sql

    def test_no_snowflake_syntax(self):
        table = _FakeTable()
        sql, _ = generate_pg_create_table(table, "ecommerce_dwh")

        assert "COMMENT '" not in sql
        assert "CLUSTER BY" not in sql
        assert "NUMBER(" not in sql
        assert "TIMESTAMP_NTZ" not in sql

    def test_table_comment_generated(self):
        table = _FakeTable()
        _, comments = generate_pg_create_table(table, "ecommerce_dwh")

        table_comments = [c for c in comments if "COMMENT ON TABLE" in c]
        assert len(table_comments) == 1
        assert "ecommerce_dwh.dim_test" in table_comments[0]
        assert "Test dimension table" in table_comments[0]

    def test_column_comments_generated(self):
        table = _FakeTable()
        _, comments = generate_pg_create_table(table, "ecommerce_dwh")

        col_comments = [c for c in comments if "COMMENT ON COLUMN" in c]
        assert len(col_comments) == 3  # test_key, test_id, amount have comments

    def test_single_quote_escaping(self):
        class TableWithQuote(BaseTable):
            table_name = "dim_quoted"
            schema_name = "s"
            comment = "Table with 'single' quotes"
            primary_key = ["k"]
            foreign_keys = []

            def define_columns(self):
                return [Column(name="k", data_type="NUMBER", precision=38, scale=0, comment="It's a key")]

        table = TableWithQuote()
        _, comments = generate_pg_create_table(table, "s")

        for c in comments:
            assert "\\'" not in c  # should use '' not \'
            if "It" in c:
                assert "It''s a key" in c


class TestGeneratePgDropTable:

    def test_drop_table(self):
        table = _FakeTable()
        sql = generate_pg_drop_table(table, "ecommerce_dwh")
        assert sql == "DROP TABLE IF EXISTS ecommerce_dwh.dim_test CASCADE;"


class TestGeneratePgForeignKeys:

    def test_fk_generation(self):
        table = _FakeTableWithFK()
        fk_stmts = generate_pg_foreign_keys(table, "ecommerce_dwh")

        assert len(fk_stmts) == 2

        assert "ALTER TABLE ecommerce_dwh.fact_test" in fk_stmts[0]
        assert "REFERENCES ecommerce_dwh.dim_test(test_key)" in fk_stmts[0]
        assert "fk_fact_test_test_key" in fk_stmts[0]

    def test_fk_on_delete_cascade(self):
        table = _FakeTableWithFK()
        fk_stmts = generate_pg_foreign_keys(table, "ecommerce_dwh")

        cascade_fk = [s for s in fk_stmts if "dim_dates" in s][0]
        assert "ON DELETE CASCADE" in cascade_fk

    def test_fk_uses_two_part_names(self):
        table = _FakeTableWithFK()
        fk_stmts = generate_pg_foreign_keys(table, "myschema")

        for stmt in fk_stmts:
            assert "myschema." in stmt
            # No 3-part name
            assert stmt.count(".") <= 4  # schema.table and schema.ref_table in one stmt

    def test_empty_fk_list(self):
        table = _FakeTable()
        assert generate_pg_foreign_keys(table, "s") == []
