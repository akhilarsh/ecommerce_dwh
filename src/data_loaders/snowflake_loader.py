"""
Snowflake data loader implementation.

Uses write_pandas for small/medium datasets and COPY INTO for large datasets.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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
            
            if method == LoadMethod.STAGED and len(df) >= self.config.staged_load_threshold:
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
