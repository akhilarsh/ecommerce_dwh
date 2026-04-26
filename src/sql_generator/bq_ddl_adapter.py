"""
BigQuery DDL adapter.

Transforms BaseTable model definitions into BigQuery-compatible DDL
without modifying existing Snowflake / PG / Databricks DDL logic.

Design decisions (see plans/phase12_bigquery.md):
- 3-part qualified names with backticks (`project.dataset.table`).
- Native semi-structured: VARIANT/OBJECT/ARRAY -> JSON.
- Native geospatial: GEOGRAPHY (BigQuery is the only target with first-class geo).
- BINARY -> BYTES (base64 input handled in the loader).
- VARCHAR(n) -> STRING (length dropped — BigQuery STRING is unbounded).
- TIMESTAMP_NTZ -> DATETIME (no timezone).
- PK / FK as informational constraints (NOT ENFORCED) — supported by BigQuery
  query optimizer and BI tools.
- Comments via column-level and table-level `OPTIONS (description = '...')`.
"""

from typing import List, Optional, Tuple

from src.models.base_table import BaseTable, Column
from src.utils.logger import get_logger

logger = get_logger(__name__)


def map_column_to_bq(col: Column) -> str:
    """
    Map a Snowflake column definition to a BigQuery SQL column fragment.

    Returns the full column clause including inline OPTIONS, e.g.:
        customer_key INT64 NOT NULL OPTIONS (description = 'Surrogate key')
    """
    bq_type = _map_type(col.data_type, col.length, col.precision, col.scale)

    parts = [col.name, bq_type]

    # BigQuery's column-definition grammar requires this exact ordering:
    #   <type> [DEFAULT expr] [NOT NULL] [OPTIONS(...)]
    # Putting NOT NULL before DEFAULT triggers "Expected ')' or ',' but got
    # keyword DEFAULT" — confirmed against real BigQuery during Phase 12 setup.
    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")

    if not col.nullable:
        parts.append("NOT NULL")

    if col.comment:
        parts.append(f"OPTIONS (description = '{_escape_bq(col.comment)}')")

    return " ".join(parts)


def _map_type(
    data_type: str,
    length: Optional[int],
    precision: Optional[int],
    scale: Optional[int],
) -> str:
    """Map Snowflake data type to BigQuery equivalent."""
    dt = data_type.upper().strip()

    if dt == "VARCHAR":
        # BigQuery STRING is unbounded; length is dropped.
        return "STRING"

    if dt == "NUMBER":
        if precision is not None and scale is not None and scale > 0:
            return f"NUMERIC({precision},{scale})"

        p = precision or 38

        # Surrogate-key convention: NUMBER(38,0) is used throughout the
        # codebase as a "big int". Match Databricks' BIGINT and Snowflake's
        # NUMBER(38,0) by collapsing to INT64 — it's the same 8-byte signed
        # integer in BigQuery and never overflows for our key ranges.
        if p == 38:
            return "INT64"
        # BigQuery INT64 holds 19 digits (2^63 - 1). p > 18 needs BIGNUMERIC.
        if p <= 18:
            return "INT64"
        return f"BIGNUMERIC({p})"

    if dt == "TIMESTAMP_NTZ":
        # BigQuery DATETIME has no timezone; TIMESTAMP would be UTC-anchored.
        return "DATETIME"

    if dt == "TIMESTAMP":
        return "TIMESTAMP"

    if dt == "DATE":
        return "DATE"

    if dt == "TIME":
        return "TIME"

    if dt == "BOOLEAN":
        return "BOOL"

    if dt == "FLOAT":
        return "FLOAT64"

    # Semi-structured — native JSON (no parse_json wrapper at insert time).
    if dt in ("VARIANT", "OBJECT", "ARRAY"):
        return "JSON"

    if dt in ("BINARY", "VARBINARY"):
        return "BYTES"

    # Native geospatial.
    if dt in ("GEOGRAPHY", "GEOMETRY"):
        return "GEOGRAPHY"

    return dt


def _qualified(project: str, dataset: str, table_name: str) -> str:
    """Build a backtick-quoted 3-part qualified name."""
    return f"`{project}.{dataset}.{table_name}`"


def generate_bq_create_table(
    table: BaseTable,
    project: str,
    dataset: str,
) -> Tuple[str, List[str]]:
    """
    Generate BigQuery CREATE TABLE statement with inline column comments.

    Args:
        table: BaseTable instance
        project: GCP project id
        dataset: BigQuery dataset name

    Returns:
        (create_sql, comment_statements) — comment_statements is always empty
        for BigQuery (comments are inline via OPTIONS). Tuple matches the
        pg / dbx adapter signature so callers can treat them the same way.
    """
    qualified_name = _qualified(project, dataset, table.table_name)
    columns = table.define_columns()

    column_defs = [f"  {map_column_to_bq(col)}" for col in columns]

    if table.primary_key:
        pk_cols = ", ".join(table.primary_key)
        # BigQuery rejects `CONSTRAINT name PRIMARY KEY (...) NOT ENFORCED` in
        # the column list — only the unnamed form is valid for table-level PKs.
        # Confirmed via live BigQuery 400 syntax error during Phase 12 smoke test.
        column_defs.append(f"  PRIMARY KEY ({pk_cols}) NOT ENFORCED")

    columns_sql = ",\n".join(column_defs)

    create_sql = (
        f"CREATE TABLE IF NOT EXISTS {qualified_name} (\n"
        f"{columns_sql}\n"
        f")"
    )

    if table.comment:
        create_sql += f"\nOPTIONS (description = '{_escape_bq(table.comment)}')"

    create_sql += ";"

    # Comments are inline via column OPTIONS; no separate COMMENT ON statements.
    return create_sql, []


def generate_bq_drop_table(
    table: BaseTable,
    project: str,
    dataset: str,
) -> str:
    """Generate BigQuery DROP TABLE statement."""
    return f"DROP TABLE IF EXISTS {_qualified(project, dataset, table.table_name)};"


def generate_bq_foreign_keys(
    table: BaseTable,
    project: str,
    dataset: str,
) -> List[str]:
    """
    Generate BigQuery ALTER TABLE FK statements as informational constraints.

    Emits `FOREIGN KEY (...) REFERENCES ... NOT ENFORCED`. ON DELETE / ON UPDATE
    clauses are omitted because BigQuery FKs are not enforced and therefore do
    not support cascading actions.
    """
    statements: List[str] = []
    qualified_name = _qualified(project, dataset, table.table_name)

    for fk in table.foreign_keys:
        constraint_name = fk.constraint_name or f"fk_{table.table_name}_{fk.column}"
        ref_table = _qualified(project, dataset, fk.reference_table.lower())

        sql = (
            f"ALTER TABLE {qualified_name} "
            f"ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({fk.column}) "
            f"REFERENCES {ref_table}({fk.reference_column}) "
            f"NOT ENFORCED;"
        )
        statements.append(sql)

    return statements


def generate_bq_create_schema(
    project: str, dataset: str, location: Optional[str] = None
) -> str:
    """
    Generate CREATE SCHEMA IF NOT EXISTS for BigQuery.

    BigQuery datasets are created with `CREATE SCHEMA` SQL. Location must
    match the dataset's region (US, EU, etc.); if omitted BigQuery uses the
    project default.
    """
    sql = f"CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}`"
    if location:
        sql += f"\nOPTIONS (location = '{location}')"
    sql += ";"
    return sql


def _escape_bq(text: str) -> str:
    """Escape single quotes for BigQuery string literals."""
    # BigQuery accepts \\' inside single-quoted literals; doubling also works
    # in standard SQL string literals. Use doubling for parity with the
    # other adapters.
    return text.replace("'", "''")
