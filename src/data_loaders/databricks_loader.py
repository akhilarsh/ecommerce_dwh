"""
Databricks data loader implementation (Unity Catalog, SQL warehouse).

No COPY INTO — uses cursor.executemany with batched INSERT statements for
all dataset sizes. Small DataFrames are loaded in a single batch; larger
ones are chunked by LoaderConfig.batch_size.
"""

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.connectors.databricks_connector import DatabricksConnector
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
)
from src.utils.logger import get_logger

logger = get_logger("loader.databricks")


class DatabricksLoader(BaseDataLoader):
    """
    Databricks-specific data loader.

    Uses cursor.executemany with chunked INSERT for all loads. Dataset-size
    handling is governed by LoaderConfig.batch_size and staged_load_threshold
    (which only controls the reported LoadMethod — the underlying path is
    the same).

    Usage:
        with DatabricksConnector() as connector:
            loader = DatabricksLoader(connector)
            result = loader.load_dataframe(df, "dim_customers")
    """

    def __init__(
        self,
        connector: DatabricksConnector,
        config: Optional[LoaderConfig] = None,
    ):
        super().__init__(config)
        self.connector = connector

        if not self.config.database:
            self.config.database = connector.catalog
        if not self.config.schema:
            self.config.schema = connector.schema or "ecommerce_dwh"

    @property
    def platform_name(self) -> str:
        return "databricks"

    def load_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        **kwargs,
    ) -> LoadResult:
        start_time = time.time()
        started_at = datetime.now()

        validation_errors = self._validate_dataframe(df, table_name)
        if validation_errors:
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.DATAFRAME,
                errors=validation_errors,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        method = self._select_load_method(len(df))

        try:
            if self.config.truncate_before_load:
                self.truncate_table(table_name)

            result = self._load_via_executemany(df, table_name, method)

            duration = time.time() - start_time
            result.duration_seconds = duration
            result.started_at = started_at
            result.completed_at = datetime.now()

            if self.config.validate_after_load and result.success:
                actual_count = self.get_row_count(table_name)
                if not self.config.truncate_before_load:
                    self._logger.debug(
                        f"{table_name}: {actual_count} total rows after load"
                    )
                elif actual_count != result.rows_loaded:
                    result.warnings.append(
                        f"Row count mismatch: expected {result.rows_loaded}, "
                        f"got {actual_count}"
                    )

            self._logger.info(str(result))
            return result

        except Exception as e:
            duration = time.time() - start_time
            self._logger.error(f"Failed to load {table_name}: {e}")
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=method,
                duration_seconds=duration,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now(),
            )

    def _qualified(self, table_name: str) -> str:
        return f"{self.config.database}.{self.config.schema}.{table_name}"

    def _get_column_types(self, table_name: str) -> Dict[str, str]:
        """
        Fetch {column_name: data_type} for the target table.

        Uses DESCRIBE TABLE rather than parameterized information_schema
        because system-table parameter binding has been unreliable.
        """
        qualified = self._qualified(table_name)
        try:
            result = self.connector.execute_query(f"DESCRIBE TABLE {qualified}")
            types: Dict[str, str] = {}
            for row in result or []:
                col_name = row[0] if row and len(row) > 0 else None
                data_type = row[1] if len(row) > 1 else ""
                if not col_name:
                    continue
                # DESCRIBE TABLE returns a header divider followed by partition
                # info — both prefixed with "#" — skip them.
                if col_name.startswith("#") or col_name.strip() == "":
                    continue
                # Once we hit a "# Partition Information" or similar section,
                # stop processing further rows.
                normalized = (data_type or "").upper().split("(")[0].strip()
                types[col_name.lower()] = normalized

            special = {k: v for k, v in types.items() if v in ("VARIANT", "BINARY")}
            if special:
                self._logger.info(
                    f"{table_name} special-type columns: {special}"
                )
            else:
                self._logger.debug(f"{table_name} column types: {types}")
            return types
        except Exception as e:
            self._logger.warning(
                f"Could not fetch column types for {table_name}: {e}; "
                "falling back to plain placeholders"
            )
            return {}

    def _placeholder_for(
        self, index: int, column_name: str, column_types: Dict[str, str]
    ) -> str:
        """
        Build the named placeholder expression for one column.

        databricks-sql-connector v4 uses paramstyle "named" (:name), not qmark.
        VARIANT columns need parse_json(:p) and BINARY columns need
        unbase64(:p) — the parameter value must be a JSON string or base64
        ASCII string respectively.
        """
        param = f":p{index}"
        dtype = column_types.get(column_name.lower(), "")
        if dtype == "VARIANT":
            return f"parse_json({param})"
        if dtype == "BINARY":
            return f"unbase64({param})"
        return param

    def _load_via_executemany(
        self,
        df: pd.DataFrame,
        table_name: str,
        method: LoadMethod,
    ) -> LoadResult:
        """
        Multi-row inline INSERT — one statement per chunk.

        Named-paramstyle executemany on databricks-sql-connector executes
        per-row, which is ~1 round-trip per row over a SQL warehouse and
        crawls on tables like fact_inventory_snapshots (~750K rows). Inlining
        values into a single INSERT VALUES (...), (...), ... statement is
        ~100-1000x faster.

        Statement-size cap: Databricks SQL allows statements up to ~16 MB.
        We chunk by both row count (config.batch_size) and a soft byte budget
        to stay well under that.
        """
        qualified = self._qualified(table_name)
        columns = list(df.columns)
        column_types = self._get_column_types(table_name)

        columns_sql = ", ".join(columns)
        col_types = [column_types.get(c.lower(), "") for c in columns]

        self._logger.debug(
            f"Loading {len(df)} rows to {table_name} via inline INSERT "
            f"(batch_size={self.config.batch_size})"
        )

        # Soft byte budget per statement (well under Databricks' ~16 MB cap).
        BYTE_BUDGET = 4 * 1024 * 1024

        rows = list(df.itertuples(index=False, name=None))
        batch_size = max(1, self.config.batch_size)
        total_loaded = 0
        i = 0
        while i < len(rows):
            tuples_sql: List[str] = []
            chunk_bytes = 0
            chunk_end = min(i + batch_size, len(rows))
            j = i
            while j < chunk_end:
                row = rows[j]
                literals = [
                    _to_sql_literal(v, col_types[k]) for k, v in enumerate(row)
                ]
                tuple_sql = "(" + ", ".join(literals) + ")"
                # Always include at least one row per statement, even if it
                # exceeds the byte budget on its own.
                if tuples_sql and chunk_bytes + len(tuple_sql) > BYTE_BUDGET:
                    break
                tuples_sql.append(tuple_sql)
                chunk_bytes += len(tuple_sql) + 2  # ", " separator
                j += 1

            insert_sql = (
                f"INSERT INTO {qualified} ({columns_sql}) VALUES "
                + ",\n".join(tuples_sql)
            )
            self.connector.cursor.execute(insert_sql)
            total_loaded += len(tuples_sql)
            i = j

        return LoadResult(
            table_name=table_name,
            rows_loaded=total_loaded,
            success=True,
            method=method,
        )

    def load_csv(
        self,
        filepath: Path,
        table_name: str,
        **kwargs,
    ) -> LoadResult:
        start_time = time.time()
        started_at = datetime.now()
        filepath = Path(filepath)

        if not filepath.exists():
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.STAGED,
                errors=[f"File not found: {filepath}"],
                started_at=started_at,
                completed_at=datetime.now(),
            )

        try:
            df = pd.read_csv(filepath)
            result = self.load_dataframe(df, table_name, **kwargs)
            # Preserve original started_at; update duration only if load_dataframe
            # didn't already set everything.
            result.started_at = started_at
            result.completed_at = datetime.now()
            result.duration_seconds = time.time() - start_time
            return result

        except Exception as e:
            duration = time.time() - start_time
            self._logger.error(f"Failed to load {table_name} from CSV: {e}")
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.STAGED,
                duration_seconds=duration,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now(),
            )

    def truncate_table(self, table_name: str) -> None:
        qualified = self._qualified(table_name)
        sql = f"TRUNCATE TABLE {qualified}"

        self._logger.debug(f"Truncating {qualified}")
        self.connector.execute_query(sql)
        self._logger.info(f"Truncated {table_name}")

    def get_row_count(self, table_name: str) -> int:
        qualified = self._qualified(table_name)
        sql = f"SELECT COUNT(*) FROM {qualified}"

        result = self.connector.execute_query(sql)
        return result[0][0] if result else 0

    def table_exists(self, table_name: str) -> bool:
        return self.connector.table_exists(table_name, schema=self.config.schema)


def _dataframe_to_tuples(df: pd.DataFrame) -> List[Tuple[Any, ...]]:
    """Convert DataFrame rows to tuples with NaN replaced by None."""
    return [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df.itertuples(index=False, name=None)
    ]


def _coerce_value(v: Any) -> Any:
    """
    Coerce numpy/pandas scalar types to native Python types that the
    databricks-sql-connector parameter binding accepts.
    """
    # numpy scalars expose .item() to convert to native Python types
    if hasattr(v, "item") and not isinstance(v, (str, bytes, bytearray)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            pass
    return v


def _sql_quote(s: str) -> str:
    """Escape a Python str for use as a Databricks SQL string literal."""
    # Databricks accepts either '' or \\' for embedded single quotes; doubling
    # is safer because it doesn't interact with backslash-escape settings.
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def _to_sql_literal(v: Any, sql_type: str) -> str:
    """
    Render a Python value as a Databricks SQL literal expression.

    `sql_type` is the column's data type (uppercase, no parens) from
    DESCRIBE TABLE — used to wrap VARIANT/BINARY values appropriately.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return "NULL"

    v = _coerce_value(v)

    if sql_type == "VARIANT":
        # Value is expected to be a JSON string (the data generator emits
        # json.dumps(...)). Escape and wrap in parse_json('...').
        return f"parse_json({_sql_quote(str(v))})"

    if sql_type == "BINARY":
        # Value is base64-encoded ASCII; decode server-side via unbase64.
        return f"unbase64({_sql_quote(str(v))})"

    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"

    if isinstance(v, (int, float)):
        return repr(v)

    if isinstance(v, pd.Timestamp):
        # TIMESTAMP literal: ISO-formatted with space separator
        return f"TIMESTAMP{_sql_quote(v.strftime('%Y-%m-%d %H:%M:%S'))}"

    if isinstance(v, datetime):
        return f"TIMESTAMP{_sql_quote(v.strftime('%Y-%m-%d %H:%M:%S'))}"

    if isinstance(v, date):
        return f"DATE{_sql_quote(v.isoformat())}"

    # Default: STRING (or unknown type) — quote as string literal.
    s = str(v)
    # Heuristic for date/timestamp strings coming from CSV (no native dtype).
    if sql_type == "DATE" and len(s) == 10 and s[4] == "-":
        return f"DATE{_sql_quote(s)}"
    if sql_type in ("TIMESTAMP", "TIMESTAMP_NTZ") and len(s) >= 19 and s[4] == "-":
        # Trim trailing fractional seconds beyond microseconds
        return f"TIMESTAMP{_sql_quote(s[:26] if '.' in s else s[:19])}"

    return _sql_quote(s)
