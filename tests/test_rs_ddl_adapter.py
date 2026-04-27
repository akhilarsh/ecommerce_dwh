"""Tests for Redshift DDL adapter type mapping and DDL generation."""

import pytest

from src.models.base_table import BaseTable, Column, ForeignKey
from src.sql_generator.rs_ddl_adapter import (
    _map_type,
    map_column_to_rs,
    generate_rs_create_table,
    generate_rs_drop_table,
    generate_rs_foreign_keys,
    generate_rs_create_schema,
    RS_VARCHAR_MAX,
)


class TestTypeMapping:

    def test_number_38_to_bigint(self):
        # NUMBER(38,0) is the codebase's surrogate-key convention.
        assert _map_type("NUMBER", None, 38, 0) == "BIGINT"

    def test_number_38_no_scale_to_bigint(self):
        assert _map_type("NUMBER", None, 38, None) == "BIGINT"

    def test_number_smallint_range(self):
        assert _map_type("NUMBER", None, 1, 0) == "SMALLINT"
        assert _map_type("NUMBER", None, 4, 0) == "SMALLINT"

    def test_number_integer_range(self):
        assert _map_type("NUMBER", None, 5, 0) == "INTEGER"
        assert _map_type("NUMBER", None, 9, 0) == "INTEGER"

    def test_number_bigint_range(self):
        assert _map_type("NUMBER", None, 10, 0) == "BIGINT"
        assert _map_type("NUMBER", None, 18, 0) == "BIGINT"

    def test_number_19_to_numeric(self):
        # 19 < precision < 38 collapses to NUMERIC(p,0).
        assert _map_type("NUMBER", None, 19, 0) == "NUMERIC(19,0)"
        assert _map_type("NUMBER", None, 25, 0) == "NUMERIC(25,0)"

    def test_number_with_scale_to_numeric(self):
        assert _map_type("NUMBER", None, 15, 2) == "NUMERIC(15,2)"
        assert _map_type("NUMBER", None, 10, 6) == "NUMERIC(10,6)"

    def test_varchar_with_length_preserved(self):
        assert _map_type("VARCHAR", 100, None, None) == "VARCHAR(100)"
        assert _map_type("VARCHAR", 255, None, None) == "VARCHAR(255)"

    def test_varchar_no_length_uses_max(self):
        assert _map_type("VARCHAR", None, None, None) == f"VARCHAR({RS_VARCHAR_MAX})"

    def test_varchar_oversize_clamped(self):
        # Anything above 65535 must be clamped — Redshift rejects larger.
        result = _map_type("VARCHAR", 100000, None, None)
        assert result == f"VARCHAR({RS_VARCHAR_MAX})"

    def test_timestamp_ntz_to_timestamp(self):
        # TIMESTAMP_NTZ (no timezone) maps to Redshift TIMESTAMP.
        assert _map_type("TIMESTAMP_NTZ", None, None, None) == "TIMESTAMP"

    def test_timestamp_to_timestamptz(self):
        # Snowflake TIMESTAMP (TZ-aware) -> TIMESTAMPTZ.
        assert _map_type("TIMESTAMP", None, None, None) == "TIMESTAMPTZ"

    def test_date_passthrough(self):
        assert _map_type("DATE", None, None, None) == "DATE"

    def test_time_passthrough(self):
        assert _map_type("TIME", None, None, None) == "TIME"

    def test_boolean_passthrough(self):
        assert _map_type("BOOLEAN", None, None, None) == "BOOLEAN"

    def test_float_to_double_precision(self):
        assert _map_type("FLOAT", None, None, None) == "DOUBLE PRECISION"

    def test_variant_to_super(self):
        # Native SUPER type — no JSON_PARSE wrapper at column level.
        assert _map_type("VARIANT", None, None, None) == "SUPER"

    def test_object_to_super(self):
        assert _map_type("OBJECT", None, None, None) == "SUPER"

    def test_array_to_super(self):
        assert _map_type("ARRAY", None, None, None) == "SUPER"

    def test_binary_to_varbyte(self):
        assert _map_type("BINARY", None, None, None) == "VARBYTE"

    def test_geography_native(self):
        assert _map_type("GEOGRAPHY", None, None, None) == "GEOGRAPHY"

    def test_geometry_native(self):
        assert _map_type("GEOMETRY", None, None, None) == "GEOMETRY"


class TestMapColumnToRs:

    def test_basic_column(self):
        col = Column(name="id", data_type="NUMBER", precision=18, scale=0, nullable=False)
        assert map_column_to_rs(col) == "id BIGINT NOT NULL"

    def test_column_with_default(self):
        col = Column(name="active", data_type="BOOLEAN", default="FALSE")
        assert map_column_to_rs(col) == "active BOOLEAN DEFAULT FALSE"

    def test_default_after_not_null(self):
        col = Column(
            name="is_featured", data_type="BOOLEAN", nullable=False, default="FALSE"
        )
        result = map_column_to_rs(col)
        # Redshift accepts both orderings; we put NOT NULL first like Postgres.
        assert "is_featured BOOLEAN" in result
        assert "NOT NULL" in result
        assert "DEFAULT FALSE" in result

    def test_varchar_keeps_length(self):
        col = Column(name="name", data_type="VARCHAR", length=255, nullable=False)
        assert map_column_to_rs(col) == "name VARCHAR(255) NOT NULL"

    def test_super_column(self):
        col = Column(name="preferences", data_type="VARIANT", comment="User prefs")
        # Comments go to separate COMMENT ON statements; not inline.
        assert map_column_to_rs(col) == "preferences SUPER"

    def test_geography_column(self):
        col = Column(name="home_location", data_type="GEOGRAPHY")
        assert map_column_to_rs(col) == "home_location GEOGRAPHY"

    def test_varbyte_column(self):
        col = Column(name="raw_payload", data_type="BINARY")
        assert map_column_to_rs(col) == "raw_payload VARBYTE"


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


class TestGenerateRsCreateTable:

    def test_two_part_qualified_name(self):
        sql, _ = generate_rs_create_table(_FakeTable(), "e_mart")
        assert "CREATE TABLE IF NOT EXISTS e_mart.dim_test" in sql

    def test_column_mappings_in_create(self):
        sql, _ = generate_rs_create_table(_FakeTable(), "e_mart")
        assert "test_key BIGINT NOT NULL" in sql
        assert "test_id VARCHAR(50) NOT NULL" in sql
        assert "amount NUMERIC(15,2)" in sql
        assert "preferences SUPER" in sql
        assert "home_location GEOGRAPHY" in sql
        assert "raw_payload VARBYTE" in sql
        assert "created_at TIMESTAMP NOT NULL" in sql
        assert "is_active BOOLEAN DEFAULT TRUE" in sql

    def test_diststyle_auto_emitted(self):
        sql, _ = generate_rs_create_table(_FakeTable(), "e_mart")
        assert "DISTSTYLE AUTO" in sql
        # No manual SORTKEY (Q5 decision).
        assert "SORTKEY" not in sql

    def test_primary_key_inline(self):
        sql, _ = generate_rs_create_table(_FakeTable(), "e_mart")
        assert "PRIMARY KEY (test_key)" in sql
        # NOT ENFORCED keyword is rejected by Redshift; must be absent.
        assert "NOT ENFORCED" not in sql

    def test_table_comment_in_separate_statement(self):
        sql, comments = generate_rs_create_table(_FakeTable(), "e_mart")
        # Inline COMMENT (Databricks-style) must NOT appear in CREATE.
        assert "COMMENT '" not in sql
        # Should be a separate COMMENT ON TABLE statement.
        joined = "\n".join(comments)
        assert "COMMENT ON TABLE e_mart.dim_test IS 'Test dimension table';" in joined

    def test_column_comments_in_separate_statements(self):
        _, comments = generate_rs_create_table(_FakeTable(), "e_mart")
        joined = "\n".join(comments)
        assert "COMMENT ON COLUMN e_mart.dim_test.test_key IS 'Surrogate key';" in joined
        assert "COMMENT ON COLUMN e_mart.dim_test.test_id IS 'Business key';" in joined

    def test_no_other_platform_syntax(self):
        sql, _ = generate_rs_create_table(_FakeTable(), "e_mart")
        # No Snowflake / Databricks / BigQuery artifacts.
        assert "AUTOINCREMENT" not in sql
        assert "USING DELTA" not in sql
        assert "TBLPROPERTIES" not in sql
        assert "RELY" not in sql
        assert "OPTIONS (" not in sql
        assert "TIMESTAMP WITHOUT TIME ZONE" not in sql

    def test_single_quote_escaping_in_comments(self):
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

        _, comments = generate_rs_create_table(_T(), "e_mart")
        joined = "\n".join(comments)
        assert "Table with ''single'' quotes" in joined
        assert "It''s a key" in joined


class TestGenerateRsDropTable:

    def test_drop_table_two_part_with_cascade(self):
        sql = generate_rs_drop_table(_FakeTable(), "e_mart")
        assert sql == "DROP TABLE IF EXISTS e_mart.dim_test CASCADE;"


class TestGenerateRsForeignKeys:

    def test_fk_count_and_structure(self):
        fks = generate_rs_foreign_keys(_FakeTableWithFK(), "e_mart")
        assert len(fks) == 2

        first = fks[0]
        assert "ALTER TABLE e_mart.fact_test" in first
        assert "fk_fact_test_test_key" in first
        assert "REFERENCES e_mart.dim_test(test_key)" in first

    def test_fk_omits_not_enforced_and_rely(self):
        # Redshift accepts unadorned FOREIGN KEY clauses; no NOT ENFORCED keyword.
        fks = generate_rs_foreign_keys(_FakeTableWithFK(), "e_mart")
        for fk in fks:
            assert "NOT ENFORCED" not in fk
            assert "RELY" not in fk

    def test_fk_omits_on_delete(self):
        # Redshift FKs are informational; cascading actions are not supported.
        fks = generate_rs_foreign_keys(_FakeTableWithFK(), "e_mart")
        for fk in fks:
            assert "ON DELETE" not in fk
            assert "ON UPDATE" not in fk

    def test_empty_fk_list(self):
        assert generate_rs_foreign_keys(_FakeTable(), "e_mart") == []


class TestGenerateRsCreateSchema:

    def test_create_schema_sql(self):
        sql = generate_rs_create_schema("e_mart")
        assert sql == "CREATE SCHEMA IF NOT EXISTS e_mart;"
