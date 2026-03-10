"""
PostgreSQL DDL adapter.

Transforms BaseTable model definitions into PostgreSQL-compatible DDL
without modifying existing Snowflake DDL logic.
"""

from typing import List, Optional, Tuple

from src.models.base_table import BaseTable, Column
from src.utils.logger import get_logger

logger = get_logger(__name__)


def map_column_to_pg(col: Column) -> str:
    """
    Map a Snowflake column definition to PostgreSQL SQL fragment.

    Returns:
        PostgreSQL column definition string (without comments)
    """
    pg_type = _map_type(col.data_type, col.length, col.precision, col.scale)

    parts = [col.name, pg_type]

    if not col.nullable:
        parts.append("NOT NULL")

    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")

    return " ".join(parts)


def _map_type(
    data_type: str,
    length: Optional[int],
    precision: Optional[int],
    scale: Optional[int],
) -> str:
    """Map Snowflake data type to PostgreSQL equivalent."""
    dt = data_type.upper().strip()

    if dt == "VARCHAR":
        if length:
            return f"VARCHAR({length})"
        return "VARCHAR"

    if dt == "NUMBER":
        if precision is not None and scale is not None and scale > 0:
            return f"NUMERIC({precision},{scale})"

        p = precision or 38

        if p == 38:
            return "BIGINT"
        if p <= 9:
            return "INTEGER"
        if p <= 18:
            return "BIGINT"
        return f"NUMERIC({p})"

    if dt == "TIMESTAMP_NTZ":
        return "TIMESTAMP WITHOUT TIME ZONE"

    if dt in ("BOOLEAN", "DATE", "TIME"):
        return dt

    if dt == "FLOAT":
        return "DOUBLE PRECISION"

    return dt


def generate_pg_create_table(
    table: BaseTable,
    schema: str,
) -> Tuple[str, List[str]]:
    """
    Generate PostgreSQL CREATE TABLE statement and COMMENT statements.

    Args:
        table: BaseTable instance
        schema: PostgreSQL schema name

    Returns:
        (create_sql, comment_statements) where comment_statements includes
        COMMENT ON TABLE and COMMENT ON COLUMN statements.
    """
    qualified_name = f"{schema}.{table.table_name}"
    columns = table.define_columns()

    column_defs = [f"  {map_column_to_pg(col)}" for col in columns]

    if table.primary_key:
        pk_cols = ", ".join(table.primary_key)
        column_defs.append(f"  PRIMARY KEY ({pk_cols})")

    columns_sql = ",\n".join(column_defs)
    create_sql = f"CREATE TABLE IF NOT EXISTS {qualified_name} (\n{columns_sql}\n);"

    comments: List[str] = []

    if table.comment:
        comments.append(
            f"COMMENT ON TABLE {qualified_name} IS '{_escape_pg(table.comment)}';"
        )

    for col in columns:
        if col.comment:
            comments.append(
                f"COMMENT ON COLUMN {qualified_name}.{col.name} IS '{_escape_pg(col.comment)}';"
            )

    return create_sql, comments


def generate_pg_drop_table(table: BaseTable, schema: str) -> str:
    """Generate PostgreSQL DROP TABLE statement."""
    return f"DROP TABLE IF EXISTS {schema}.{table.table_name} CASCADE;"


def generate_pg_foreign_keys(table: BaseTable, schema: str) -> List[str]:
    """
    Generate PostgreSQL ALTER TABLE FK statements.

    Uses 2-part qualified names (schema.table).
    """
    statements: List[str] = []
    qualified_name = f"{schema}.{table.table_name}"

    for fk in table.foreign_keys:
        constraint_name = fk.constraint_name or f"fk_{table.table_name}_{fk.column}"
        ref_table = f"{schema}.{fk.reference_table.lower()}"

        sql = (
            f"ALTER TABLE {qualified_name} "
            f"ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({fk.column}) "
            f"REFERENCES {ref_table}({fk.reference_column})"
        )

        if fk.on_delete != "RESTRICT":
            sql += f" ON DELETE {fk.on_delete}"
        if fk.on_update != "RESTRICT":
            sql += f" ON UPDATE {fk.on_update}"

        sql += ";"
        statements.append(sql)

    return statements


def _escape_pg(text: str) -> str:
    """Escape single quotes for PostgreSQL string literals."""
    return text.replace("'", "''")
