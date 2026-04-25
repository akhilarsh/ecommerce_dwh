"""
Databricks DDL adapter (Unity Catalog only, DBR 15.3+ required for VARIANT).

Transforms BaseTable model definitions into Databricks-compatible DDL
without modifying existing Snowflake DDL logic.

Design decisions (see plans/phase11_databricks.md):
- Unity Catalog only — no hive_metastore support.
- 3-part qualified names (catalog.schema.table).
- Delta tables (USING DELTA).
- Informational PK inline, informational FK via ALTER TABLE (NOT ENFORCED RELY).
- Native VARIANT for semi-structured columns (requires DBR 15.3+).
- Comments emitted inline (no separate COMMENT ON statements).
"""

from typing import List, Optional, Tuple

from src.models.base_table import BaseTable, Column
from src.utils.logger import get_logger

logger = get_logger(__name__)


def map_column_to_dbx(col: Column) -> str:
    """
    Map a Snowflake column definition to a Databricks SQL column fragment.

    Returns the full column clause including inline comment, e.g.:
        customer_key BIGINT NOT NULL COMMENT 'Surrogate key'
    """
    dbx_type = _map_type(col.data_type, col.length, col.precision, col.scale)

    parts = [col.name, dbx_type]

    if not col.nullable:
        parts.append("NOT NULL")

    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")

    if col.comment:
        parts.append(f"COMMENT '{_escape_dbx(col.comment)}'")

    return " ".join(parts)


def _map_type(
    data_type: str,
    length: Optional[int],
    precision: Optional[int],
    scale: Optional[int],
) -> str:
    """Map Snowflake data type to Databricks equivalent."""
    dt = data_type.upper().strip()

    if dt == "VARCHAR":
        # Databricks STRING has no length constraint; length is dropped.
        return "STRING"

    if dt == "NUMBER":
        if precision is not None and scale is not None and scale > 0:
            return f"DECIMAL({precision},{scale})"

        p = precision or 38

        if p == 38:
            return "BIGINT"
        if p <= 9:
            return "INT"
        if p <= 18:
            return "BIGINT"
        return f"DECIMAL({p},0)"

    if dt == "TIMESTAMP_NTZ":
        return "TIMESTAMP_NTZ"

    if dt == "TIMESTAMP":
        return "TIMESTAMP"

    if dt == "DATE":
        return "DATE"

    if dt == "TIME":
        # Databricks has no native TIME type; store as STRING.
        return "STRING"

    if dt == "BOOLEAN":
        return "BOOLEAN"

    if dt == "FLOAT":
        return "DOUBLE"

    # Semi-structured — native VARIANT on DBR 15.3+ / Unity Catalog.
    if dt in ("VARIANT", "OBJECT", "ARRAY"):
        return "VARIANT"

    if dt in ("BINARY", "VARBINARY"):
        return "BINARY"

    # Databricks has no GEOGRAPHY/GEOMETRY; store as STRING (WKT/GeoJSON).
    if dt in ("GEOGRAPHY", "GEOMETRY"):
        return "STRING"

    return dt


def generate_dbx_create_table(
    table: BaseTable,
    catalog: str,
    schema: str,
) -> Tuple[str, List[str]]:
    """
    Generate Databricks CREATE TABLE statement with inline comments.

    Args:
        table: BaseTable instance
        catalog: Unity Catalog name
        schema: Schema name

    Returns:
        (create_sql, comment_statements) — comment_statements is always empty
        for Databricks (comments are inline). Tuple matches pg_ddl_adapter
        signature so callers can treat them the same way.
    """
    qualified_name = f"{catalog}.{schema}.{table.table_name}"
    columns = table.define_columns()

    column_defs = [f"  {map_column_to_dbx(col)}" for col in columns]

    if table.primary_key:
        pk_cols = ", ".join(table.primary_key)
        pk_name = f"pk_{table.table_name}"
        column_defs.append(f"  CONSTRAINT {pk_name} PRIMARY KEY ({pk_cols}) RELY")

    columns_sql = ",\n".join(column_defs)

    create_sql = (
        f"CREATE TABLE IF NOT EXISTS {qualified_name} (\n"
        f"{columns_sql}\n"
        f")\n"
        f"USING DELTA\n"
        f"TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')"
    )

    if table.comment:
        create_sql += f"\nCOMMENT '{_escape_dbx(table.comment)}'"

    create_sql += ";"

    # Comments are inline; no separate COMMENT ON statements for Databricks.
    return create_sql, []


def generate_dbx_drop_table(
    table: BaseTable,
    catalog: str,
    schema: str,
) -> str:
    """Generate Databricks DROP TABLE statement."""
    return f"DROP TABLE IF EXISTS {catalog}.{schema}.{table.table_name};"


def generate_dbx_foreign_keys(
    table: BaseTable,
    catalog: str,
    schema: str,
) -> List[str]:
    """
    Generate Databricks ALTER TABLE FK statements as informational constraints.

    Emits `FOREIGN KEY (...) REFERENCES ... NOT ENFORCED RELY`. ON DELETE /
    ON UPDATE clauses are omitted because Delta FKs are not enforced and
    therefore do not support cascading actions.
    """
    statements: List[str] = []
    qualified_name = f"{catalog}.{schema}.{table.table_name}"

    for fk in table.foreign_keys:
        constraint_name = fk.constraint_name or f"fk_{table.table_name}_{fk.column}"
        ref_table = f"{catalog}.{schema}.{fk.reference_table.lower()}"

        sql = (
            f"ALTER TABLE {qualified_name} "
            f"ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({fk.column}) "
            f"REFERENCES {ref_table}({fk.reference_column}) "
            f"NOT ENFORCED RELY;"
        )
        statements.append(sql)

    return statements


def generate_dbx_create_schema(catalog: str, schema: str) -> str:
    """Generate CREATE SCHEMA IF NOT EXISTS for Databricks Unity Catalog."""
    return f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema};"


def _escape_dbx(text: str) -> str:
    """Escape single quotes for Databricks string literals."""
    return text.replace("'", "''")
