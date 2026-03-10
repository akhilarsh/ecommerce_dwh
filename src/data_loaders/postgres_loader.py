"""
PostgreSQL data loader implementation.

Uses execute_values for small/medium datasets and COPY FROM STDIN for large datasets.
"""

import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2.extras

from src.connectors.postgres_connector import PostgresConnector
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
)
from src.utils.logger import get_logger

logger = get_logger("loader.postgres")


class PostgresLoader(BaseDataLoader):
    """
    PostgreSQL-specific data loader.

    Uses:
    - execute_values for DataFrames < threshold (default 100K rows)
    - COPY FROM STDIN for large CSV files or DataFrames >= threshold

    Usage:
        with PostgresConnector() as connector:
            loader = PostgresLoader(connector)
            result = loader.load_dataframe(df, "dim_customers")
    """

    def __init__(
        self,
        connector: PostgresConnector,
        config: Optional[LoaderConfig] = None,
    ):
        super().__init__(config)
        self.connector = connector

        if not self.config.database:
            self.config.database = connector.database
        if not self.config.schema:
            self.config.schema = connector.schema or "public"

    @property
    def platform_name(self) -> str:
        return "postgres"

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

            if method == LoadMethod.STAGED and len(df) >= self.config.staged_load_threshold:
                result = self._load_via_copy(df, table_name)
            else:
                result = self._load_via_execute_values(df, table_name)

            duration = time.time() - start_time
            result.duration_seconds = duration
            result.started_at = started_at
            result.completed_at = datetime.now()

            if self.config.validate_after_load and result.success:
                actual_count = self.get_row_count(table_name)
                if not self.config.truncate_before_load:
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
                completed_at=datetime.now(),
            )

    def _load_via_execute_values(
        self,
        df: pd.DataFrame,
        table_name: str,
    ) -> LoadResult:
        qualified_table = f"{self.config.schema}.{table_name}"
        columns = ", ".join(df.columns)
        template = f"INSERT INTO {qualified_table} ({columns}) VALUES %s"

        self._logger.debug(f"Loading {len(df)} rows to {table_name} via execute_values")

        # Convert DataFrame to list of tuples, handling NaN -> None
        data = [
            tuple(None if pd.isna(v) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]

        psycopg2.extras.execute_values(
            self.connector.cursor,
            template,
            data,
            page_size=self.config.batch_size,
        )
        self.connector.commit()

        return LoadResult(
            table_name=table_name,
            rows_loaded=len(data),
            success=True,
            method=LoadMethod.DATAFRAME,
        )

    def _load_via_copy(
        self,
        df: pd.DataFrame,
        table_name: str,
    ) -> LoadResult:
        qualified_table = f"{self.config.schema}.{table_name}"

        self._logger.debug(f"Loading {len(df)} rows to {table_name} via COPY FROM STDIN")

        buffer = io.StringIO()
        df.to_csv(buffer, index=False, header=True)
        buffer.seek(0)

        copy_sql = (
            f"COPY {qualified_table} FROM STDIN WITH "
            f"(FORMAT csv, HEADER true, NULL '')"
        )

        self.connector.cursor.copy_expert(copy_sql, buffer)
        self.connector.commit()

        return LoadResult(
            table_name=table_name,
            rows_loaded=len(df),
            success=True,
            method=LoadMethod.STAGED,
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
            if self.config.truncate_before_load:
                self.truncate_table(table_name)

            qualified_table = f"{self.config.schema}.{table_name}"

            copy_sql = (
                f"COPY {qualified_table} FROM STDIN WITH "
                f"(FORMAT csv, HEADER true, NULL '')"
            )

            with open(filepath, "r") as f:
                self.connector.cursor.copy_expert(copy_sql, f)

            self.connector.commit()

            rows_loaded = self.get_row_count(table_name)

            duration = time.time() - start_time
            load_result = LoadResult(
                table_name=table_name,
                rows_loaded=rows_loaded,
                success=True,
                method=LoadMethod.STAGED,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=datetime.now(),
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
                completed_at=datetime.now(),
            )

    def truncate_table(self, table_name: str) -> None:
        qualified_table = f"{self.config.schema}.{table_name}"
        sql = f"TRUNCATE TABLE {qualified_table} CASCADE"

        self._logger.debug(f"Truncating {qualified_table}")
        self.connector.execute_query(sql)
        self.connector.commit()
        self._logger.info(f"Truncated {table_name}")

    def get_row_count(self, table_name: str) -> int:
        qualified_table = f"{self.config.schema}.{table_name}"
        sql = f"SELECT COUNT(*) FROM {qualified_table}"

        result = self.connector.execute_query(sql)
        return result[0][0] if result else 0

    def table_exists(self, table_name: str) -> bool:
        return self.connector.table_exists(table_name, schema=self.config.schema)
