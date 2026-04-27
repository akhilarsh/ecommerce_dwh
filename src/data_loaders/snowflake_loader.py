"""
Snowflake data loader implementation.

Uses write_pandas for small/medium datasets and COPY INTO for large datasets.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.connectors.snowflake_connector import SnowflakeConnector
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
)
from src.utils.logger import get_logger

logger = get_logger("loader.snowflake")


class SnowflakeLoader(BaseDataLoader):
    """
    Snowflake-specific data loader.
    
    Uses:
    - write_pandas for DataFrames < threshold (default 100K rows)
    - COPY INTO for large CSV files or DataFrames >= threshold
    
    Usage:
        with SnowflakeConnector() as connector:
            loader = SnowflakeLoader(connector)
            result = loader.load_dataframe(df, "dim_customers")
    """
    
    def __init__(
        self,
        connector: SnowflakeConnector,
        config: Optional[LoaderConfig] = None
    ):
        """
        Initialize Snowflake loader.
        
        Args:
            connector: Connected SnowflakeConnector instance
            config: Loader configuration
        """
        super().__init__(config)
        self.connector = connector
        
        # Use connector's database/schema if not specified in config
        if not self.config.database:
            self.config.database = connector.database
        if not self.config.schema:
            self.config.schema = connector.schema
    
    @property
    def platform_name(self) -> str:
        """Return platform name."""
        return "snowflake"
    
    def load_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        **kwargs
    ) -> LoadResult:
        """
        Load a pandas DataFrame into Snowflake.
        
        Uses write_pandas for efficiency. For very large DataFrames,
        automatically falls back to staged COPY INTO.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            **kwargs: Additional options (overwrite, auto_create_table)
            
        Returns:
            LoadResult with operation details
        """
        start_time = time.time()
        started_at = datetime.now()
        
        # Validate DataFrame
        validation_errors = self._validate_dataframe(df, table_name)
        if validation_errors:
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.DATAFRAME,
                errors=validation_errors,
                started_at=started_at,
                completed_at=datetime.now()
            )
        
        # Select method based on row count
        method = self._select_load_method(len(df))

        try:
            # Truncate if configured
            if self.config.truncate_before_load:
                self.truncate_table(table_name)

            # Tables with semi-structured / geospatial / binary columns require
            # column-level transforms (PARSE_JSON, TO_GEOGRAPHY, TO_BINARY) that
            # write_pandas cannot perform. Route them through staged COPY INTO.
            special_cols = self._get_special_columns(table_name)
            if special_cols:
                result = self._load_via_transformed_copy(df, table_name, special_cols)
            elif method == LoadMethod.STAGED and len(df) >= self.config.staged_load_threshold:
                # For very large DataFrames, save to temp file and use COPY INTO
                result = self._load_via_staging(df, table_name)
            else:
                # Use write_pandas for direct loading
                result = self._load_via_write_pandas(df, table_name)
            
            duration = time.time() - start_time
            result.duration_seconds = duration
            result.started_at = started_at
            result.completed_at = datetime.now()
            
            # Validate row count if configured
            if self.config.validate_after_load and result.success:
                actual_count = self.get_row_count(table_name)
                if not self.config.truncate_before_load:
                    # If not truncated, we can't verify exact count
                    self._logger.debug(f"{table_name}: {actual_count} total rows after load")
                elif actual_count != result.rows_loaded:
                    result.warnings.append(
                        f"Row count mismatch: expected {result.rows_loaded}, got {actual_count}"
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
                completed_at=datetime.now()
            )
    
    def _load_via_write_pandas(
        self,
        df: pd.DataFrame,
        table_name: str
    ) -> LoadResult:
        """
        Load DataFrame using Snowflake's write_pandas function.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            
        Returns:
            LoadResult
        """
        from snowflake.connector.pandas_tools import write_pandas
        
        self._logger.debug(f"Loading {len(df)} rows to {table_name} via write_pandas")
        
        success, nchunks, nrows, _ = write_pandas(
            conn=self.connector.connection,
            df=df,
            table_name=table_name.upper(),
            database=self.config.database,
            schema=self.config.schema,
            quote_identifiers=False
        )
        
        return LoadResult(
            table_name=table_name,
            rows_loaded=nrows,
            success=success,
            method=LoadMethod.DATAFRAME
        )
    
    # Snowflake types that require explicit transforms on COPY INTO from CSV.
    _TRANSFORM_TYPES = {"VARIANT", "OBJECT", "ARRAY", "GEOGRAPHY", "GEOMETRY", "BINARY", "VARBINARY"}

    def _get_column_types(self, table_name: str) -> Dict[str, str]:
        """Return ordered map of column name -> Snowflake DATA_TYPE for a table."""
        db = (self.config.database or "").upper()
        schema = (self.config.schema or "").upper()
        sql = f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM {db}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_CATALOG = '{db}'
              AND TABLE_SCHEMA = '{schema}'
              AND TABLE_NAME = '{table_name.upper()}'
            ORDER BY ORDINAL_POSITION
        """
        rows = self.connector.execute_query(sql) or []
        return {r[0].upper(): (r[1] or "").upper() for r in rows}

    def _get_special_columns(self, table_name: str) -> Dict[str, str]:
        """Return columns whose types need transforms during COPY INTO."""
        return {
            col: dtype
            for col, dtype in self._get_column_types(table_name).items()
            if dtype in self._TRANSFORM_TYPES
        }

    def _load_via_transformed_copy(
        self,
        df: pd.DataFrame,
        table_name: str,
        special_cols: Dict[str, str],
    ) -> LoadResult:
        """
        Load DataFrame via staged CSV + COPY INTO with per-column transforms.

        Required for tables containing VARIANT/OBJECT/ARRAY/GEOGRAPHY/BINARY
        columns, which write_pandas cannot populate from raw strings.
        """
        import tempfile

        self._logger.debug(
            f"Loading {len(df)} rows to {table_name} via transformed COPY INTO "
            f"(special cols: {list(special_cols)})"
        )

        # Write CSV in DDL column order so $1..$N positional refs match.
        column_types = self._get_column_types(table_name)
        ordered_cols = [c for c in column_types if c in {x.upper() for x in df.columns}]
        df_upper = df.rename(columns={c: c.upper() for c in df.columns})
        df_ordered = df_upper[ordered_cols]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as tmp_file:
            df_ordered.to_csv(tmp_file.name, index=False, header=True)
            tmp_path = Path(tmp_file.name)

        stage_name = self.config.stage_name or f"@~/{table_name}_stage"
        staged_filename = tmp_path.name + ".gz"
        qualified_table = f"{self.config.database}.{self.config.schema}.{table_name}".upper()

        try:
            put_sql = f"PUT file://{tmp_path.absolute()} {stage_name} AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
            self.connector.execute_query(put_sql)

            select_exprs = []
            for idx, col in enumerate(ordered_cols, start=1):
                dtype = column_types[col]
                if dtype in {"VARIANT", "OBJECT", "ARRAY"}:
                    select_exprs.append(f"PARSE_JSON(${idx})")
                elif dtype == "GEOGRAPHY":
                    select_exprs.append(f"TO_GEOGRAPHY(${idx})")
                elif dtype == "GEOMETRY":
                    select_exprs.append(f"TO_GEOMETRY(${idx})")
                elif dtype in {"BINARY", "VARBINARY"}:
                    select_exprs.append(f"TO_BINARY(${idx}, 'BASE64')")
                else:
                    select_exprs.append(f"${idx}")

            cols_csv = ", ".join(ordered_cols)
            select_csv = ",\n                    ".join(select_exprs)
            copy_sql = f"""
                COPY INTO {qualified_table} ({cols_csv})
                FROM (
                    SELECT
                    {select_csv}
                    FROM {stage_name}/{staged_filename}
                )
                FILE_FORMAT = (
                    TYPE = 'CSV'
                    SKIP_HEADER = 1
                    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                    NULL_IF = ('', 'NULL', 'None')
                    EMPTY_FIELD_AS_NULL = TRUE
                )
                ON_ERROR = 'ABORT_STATEMENT'
            """
            result_rows = self.connector.execute_query(copy_sql)
            rows_loaded = 0
            if result_rows:
                for row in result_rows:
                    if len(row) >= 4 and row[3]:
                        rows_loaded += row[3]

            try:
                self.connector.execute_query(f"REMOVE {stage_name}/{staged_filename}")
            except Exception as e:
                self._logger.warning(f"Failed to remove staged file: {e}")

            return LoadResult(
                table_name=table_name,
                rows_loaded=rows_loaded,
                success=True,
                method=LoadMethod.STAGED,
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _load_via_staging(
        self,
        df: pd.DataFrame,
        table_name: str
    ) -> LoadResult:
        """
        Load DataFrame via temporary file and COPY INTO.
        
        Used for very large DataFrames where staging is more efficient.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            
        Returns:
            LoadResult
        """
        import tempfile
        
        self._logger.debug(f"Loading {len(df)} rows to {table_name} via COPY INTO")
        
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.csv',
            delete=False
        ) as tmp_file:
            df.to_csv(tmp_file.name, index=False, header=True)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Load via CSV
            result = self.load_csv(tmp_path, table_name)
            return result
        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
    
    def load_csv(
        self,
        filepath: Path,
        table_name: str,
        **kwargs
    ) -> LoadResult:
        """
        Load data from CSV file using COPY INTO.
        
        Args:
            filepath: Path to CSV file
            table_name: Target table name
            **kwargs: Additional options
            
        Returns:
            LoadResult
        """
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
                completed_at=datetime.now()
            )
        
        try:
            # Truncate if configured
            if self.config.truncate_before_load:
                self.truncate_table(table_name)
            
            # Create or use existing stage
            stage_name = self.config.stage_name or f"@~/{table_name}_stage"
            
            # PUT file to stage
            put_sql = f"PUT file://{filepath.absolute()} {stage_name} AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
            self._logger.debug(f"Executing: {put_sql}")
            self.connector.execute_query(put_sql)
            
            # Get the staged file name (with compression suffix)
            staged_filename = filepath.name + ".gz"
            
            # COPY INTO table
            qualified_table = f"{self.config.database}.{self.config.schema}.{table_name}".upper()
            copy_sql = f"""
                COPY INTO {qualified_table}
                FROM {stage_name}/{staged_filename}
                FILE_FORMAT = (
                    TYPE = '{self.config.file_format}'
                    SKIP_HEADER = 1
                    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                    NULL_IF = ('', 'NULL', 'None')
                )
                ON_ERROR = 'CONTINUE'
            """
            
            self._logger.debug(f"Executing COPY INTO for {table_name}")
            result = self.connector.execute_query(copy_sql)
            
            # Parse COPY result to get row count
            rows_loaded = 0
            if result:
                # COPY INTO returns (file, status, rows_parsed, rows_loaded, ...)
                for row in result:
                    if len(row) >= 4:
                        rows_loaded += row[3] if row[3] else 0
            
            # Clean up staged file
            remove_sql = f"REMOVE {stage_name}/{staged_filename}"
            try:
                self.connector.execute_query(remove_sql)
            except Exception as e:
                self._logger.warning(f"Failed to remove staged file: {e}")
            
            duration = time.time() - start_time
            
            load_result = LoadResult(
                table_name=table_name,
                rows_loaded=rows_loaded,
                success=True,
                method=LoadMethod.STAGED,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=datetime.now()
            )
            
            self._logger.info(str(load_result))
            return load_result
            
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
                completed_at=datetime.now()
            )
    
    def truncate_table(self, table_name: str) -> None:
        """
        Truncate a table.
        
        Args:
            table_name: Table to truncate
        """
        qualified_table = f"{self.config.database}.{self.config.schema}.{table_name}".upper()
        sql = f"TRUNCATE TABLE {qualified_table}"
        
        self._logger.debug(f"Truncating {qualified_table}")
        self.connector.execute_query(sql)
        self._logger.info(f"Truncated {table_name}")
    
    def get_row_count(self, table_name: str) -> int:
        """
        Get the row count of a table.
        
        Args:
            table_name: Table name
            
        Returns:
            Number of rows
        """
        qualified_table = f"{self.config.database}.{self.config.schema}.{table_name}".upper()
        sql = f"SELECT COUNT(*) FROM {qualified_table}"
        
        result = self.connector.execute_query(sql)
        return result[0][0] if result else 0
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Table name
            
        Returns:
            True if table exists
        """
        db = self.config.database.upper() if self.config.database else ""
        schema = self.config.schema.upper() if self.config.schema else ""
        tbl = table_name.upper()
        
        sql = f"""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_CATALOG = '{db}'
            AND TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{tbl}'
        """
        
        result = self.connector.execute_query(sql)
        
        return result[0][0] > 0 if result else False
