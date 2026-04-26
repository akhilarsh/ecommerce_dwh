"""
Google BigQuery connector with context manager support.

Wraps the official `google-cloud-bigquery` Client. Project + dataset model
the catalog/schema pair from other warehouses. BigQuery has no client-side
transactions (DDL / DML autocommit), so commit() / rollback() are no-ops.

Authentication (precedence: explicit param -> env var -> ADC):

    GOOGLE_APPLICATION_CREDENTIALS  Path to a service account JSON key
    BIGQUERY_PROJECT                GCP project id  (e.g. ecommerce-db)
    BIGQUERY_DATASET                Dataset name    (default: ecommerce_dwh)
    BIGQUERY_LOCATION               Region          (default: US)

If `GOOGLE_APPLICATION_CREDENTIALS` is unset, the client falls back to
Application Default Credentials (`gcloud auth application-default login`).

The connector exposes a synchronous `execute_query` interface that mirrors
the DBAPI shape used by the other connectors. Internally it uses the
google-cloud-bigquery Client.query() job API with parameterized queries
(BigQuery's "named" parameters via `ScalarQueryParameter`).
"""

import os
from typing import Any, Dict, List, Optional, Union

from src.connectors.base_connector import BaseConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BigQueryConnector(BaseConnector):
    """
    BigQuery connection manager.

    Usage:
        with BigQueryConnector() as conn:
            conn.execute_query("SELECT 1")
    """

    PLATFORM = "bigquery"

    def __init__(
        self,
        project: Optional[str] = None,
        dataset: Optional[str] = None,
        location: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        self.project = project or os.getenv("BIGQUERY_PROJECT")
        self.dataset = dataset or os.getenv("BIGQUERY_DATASET", "ecommerce_dwh")
        self.location = location or os.getenv("BIGQUERY_LOCATION", "US")
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )

        # BigQuery is a single-project model; expose project as "database"
        # so platform-agnostic code (TableCreator, validate command) has a
        # sensible value to qualify table names with.
        self.database = self.project
        self.schema = self.dataset

        self.client = None  # google.cloud.bigquery.Client

        self._validate_config()

    def _validate_config(self) -> None:
        if not self.project:
            raise ValueError(
                "Missing required BigQuery parameter: project. "
                "Set BIGQUERY_PROJECT (or pass project=...). "
                "If using a service account, also set GOOGLE_APPLICATION_CREDENTIALS."
            )

    def _build_credentials(self):
        """Build credentials from a service account JSON file, if configured."""
        if not self.credentials_path:
            return None

        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            self.credentials_path
        )

    def connect(self) -> None:
        from google.cloud import bigquery

        try:
            auth_mode = "service_account" if self.credentials_path else "adc"
            logger.info(
                f"Connecting to BigQuery: project={self.project}, "
                f"dataset={self.dataset}, location={self.location}, auth={auth_mode}"
            )

            credentials = self._build_credentials()
            client_kwargs: Dict[str, Any] = {"project": self.project}
            if credentials is not None:
                client_kwargs["credentials"] = credentials
            if self.location:
                client_kwargs["location"] = self.location

            self.client = bigquery.Client(**client_kwargs)

            logger.info("Successfully connected to BigQuery")

        except Exception as e:
            logger.error(f"Failed to connect to BigQuery: {e}")
            raise

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
                logger.info("Connection closed")
            except Exception as e:
                logger.warning(f"Error closing BigQuery client: {e}")
            finally:
                self.client = None

    def _build_query_parameters(
        self, params: Optional[Union[tuple, Dict[str, Any]]]
    ):
        """
        Convert DBAPI-style params into BigQuery query parameters.

        - Dict[str, Any]   -> ScalarQueryParameter("name", inferred_type, value)
        - tuple / list     -> positional ScalarQueryParameter(None, ...) — only
                              usable with `?` placeholders, kept for parity with
                              the BaseConnector interface.

        Returns a list suitable for `QueryJobConfig(query_parameters=...)`,
        or None if `params` is empty.
        """
        if not params:
            return None

        from google.cloud import bigquery

        def _infer_type(v: Any) -> str:
            if isinstance(v, bool):
                return "BOOL"
            if isinstance(v, int):
                return "INT64"
            if isinstance(v, float):
                return "FLOAT64"
            if isinstance(v, bytes):
                return "BYTES"
            return "STRING"

        if isinstance(params, dict):
            return [
                bigquery.ScalarQueryParameter(name, _infer_type(value), value)
                for name, value in params.items()
            ]

        return [
            bigquery.ScalarQueryParameter(None, _infer_type(v), v) for v in params
        ]

    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[tuple]:
        if self.client is None:
            raise RuntimeError("Not connected to BigQuery. Call connect() first.")

        from google.cloud import bigquery

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            job_config = None
            qp = self._build_query_parameters(params)
            if qp is not None:
                job_config = bigquery.QueryJobConfig(query_parameters=qp)

            job = self.client.query(query, job_config=job_config)
            result_iter = job.result()  # blocks until job completes

            # DDL / DML jobs have no schema -> no rows to return.
            if result_iter.schema is None:
                logger.debug("Query executed successfully (no results)")
                return []

            results = [tuple(row.values()) for row in result_iter]
            logger.debug(f"Query returned {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            logger.error(f"Query: {query}")
            raise

    def execute_dict(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if self.client is None:
            raise RuntimeError("Not connected to BigQuery")

        from google.cloud import bigquery

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            job_config = None
            qp = self._build_query_parameters(params)
            if qp is not None:
                job_config = bigquery.QueryJobConfig(query_parameters=qp)

            job = self.client.query(query, job_config=job_config)
            result_iter = job.result()

            if result_iter.schema is None:
                return []

            results = [dict(row) for row in result_iter]
            logger.debug(f"Query returned {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise

    def execute_many(
        self,
        query: str,
        data: List[tuple],
    ) -> None:
        """
        Execute the same query for each parameter set sequentially.

        BigQuery has no batch-DML primitive equivalent to executemany, and
        per-row INSERTs are slow + rate-limited. The data loader uses
        load_table_from_dataframe instead; this method exists only to
        satisfy the BaseConnector interface and should be avoided.
        """
        if self.client is None:
            raise RuntimeError("Not connected to BigQuery")

        logger.info(f"Executing batch query with {len(data)} rows")
        for row in data:
            self.execute_query(query, row)
        logger.info("Batch execution completed")

    def commit(self) -> None:
        # BigQuery has no client-side transactions; DDL / DML autocommits.
        logger.debug("commit() called — no-op on BigQuery (autocommit)")

    def rollback(self) -> None:
        logger.warning(
            "rollback() called — no-op on BigQuery. "
            "Statements executed before this point are already committed."
        )

    def get_current_database(self) -> Optional[str]:
        return self.project

    def get_current_schema(self) -> Optional[str]:
        return self.dataset

    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        from google.cloud.exceptions import NotFound

        if self.client is None:
            raise RuntimeError("Not connected to BigQuery. Call connect() first.")

        dataset_name = schema or self.dataset
        if not dataset_name:
            raise ValueError("Dataset must be provided or set in connector")

        table_ref = f"{self.project}.{dataset_name}.{table_name}"
        try:
            self.client.get_table(table_ref)
            return True
        except NotFound:
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("Not connected to BigQuery")

        return {
            "platform": self.PLATFORM,
            "project": self.project,
            "dataset": self.dataset,
            "location": self.location,
            "auth_mode": "service_account" if self.credentials_path else "adc",
            "connected": True,
        }

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Error occurred: {exc_val}")
        self.close()
        return False
