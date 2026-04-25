"""
Databricks SQL connector with context manager support.

Uses the databricks-sql-connector library to connect to a Databricks SQL
warehouse on Unity Catalog. Autocommit is always on (Databricks SQL has
no client-side transactions), so commit()/rollback() are no-ops.

Authentication (auto-selected based on which env vars are set):
  1. OAuth M2M (preferred for service principals):
     DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET
  2. Personal Access Token (PAT, including SP on-behalf-of tokens):
     DATABRICKS_ACCESS_TOKEN

Always required:
    DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG
Optional:
    DATABRICKS_SCHEMA  (defaults to "ecommerce_dwh")
"""

import os
from typing import Any, Dict, List, Optional, Union

from src.connectors.base_connector import BaseConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabricksConnector(BaseConnector):
    """
    Databricks SQL connection manager (Unity Catalog only).

    Usage:
        with DatabricksConnector() as conn:
            conn.execute_query("SELECT 1")
    """

    PLATFORM = "databricks"

    def __init__(
        self,
        server_hostname: Optional[str] = None,
        http_path: Optional[str] = None,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        self.server_hostname = server_hostname or os.getenv("DATABRICKS_SERVER_HOSTNAME")
        self.http_path = http_path or os.getenv("DATABRICKS_HTTP_PATH")
        self.access_token = access_token or os.getenv("DATABRICKS_ACCESS_TOKEN")
        self.client_id = client_id or os.getenv("DATABRICKS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("DATABRICKS_CLIENT_SECRET")
        self.catalog = catalog or os.getenv("DATABRICKS_CATALOG")
        self.schema = schema or os.getenv("DATABRICKS_SCHEMA", "ecommerce_dwh")

        # Databricks SQL is a single-database model; expose catalog as "database"
        # so platform-agnostic code (tests, TableCreator) has a sensible value.
        self.database = self.catalog

        # OAuth M2M takes precedence when both client_id+secret and a PAT are set.
        self.auth_mode = (
            "oauth_m2m"
            if (self.client_id and self.client_secret)
            else "pat"
        )

        self.connection = None
        self.cursor = None

        self._validate_config()

    def _validate_config(self) -> None:
        base_required = {
            "server_hostname": self.server_hostname,
            "http_path": self.http_path,
            "catalog": self.catalog,
        }
        missing = [k for k, v in base_required.items() if not v]

        if self.auth_mode == "oauth_m2m":
            if not self.client_id:
                missing.append("client_id")
            if not self.client_secret:
                missing.append("client_secret")
        else:
            if not self.access_token:
                missing.append("access_token (or client_id+client_secret)")

        if missing:
            raise ValueError(
                f"Missing required Databricks parameters: {', '.join(missing)}. "
                "Set DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, "
                "DATABRICKS_CATALOG, and either DATABRICKS_ACCESS_TOKEN (PAT) or "
                "DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET (OAuth M2M)."
            )

    def _oauth_credentials_provider(self):
        """Build an OAuth M2M credentials provider for service principals."""
        from databricks.sdk.core import Config, oauth_service_principal

        host = self.server_hostname
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"

        def provider():
            config = Config(
                host=host,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            return oauth_service_principal(config)

        return provider

    def connect(self) -> None:
        from databricks import sql as dbsql

        try:
            logger.info(
                f"Connecting to Databricks: {self.server_hostname} "
                f"(catalog={self.catalog}, schema={self.schema}, auth={self.auth_mode})"
            )

            connect_kwargs = {
                "server_hostname": self.server_hostname,
                "http_path": self.http_path,
            }

            if self.auth_mode == "oauth_m2m":
                connect_kwargs["credentials_provider"] = self._oauth_credentials_provider()
            else:
                connect_kwargs["access_token"] = self.access_token

            self.connection = dbsql.connect(**connect_kwargs)
            self.cursor = self.connection.cursor()

            if self.catalog:
                self.cursor.execute(f"USE CATALOG `{self.catalog}`")
            if self.schema:
                self.cursor.execute(f"USE SCHEMA `{self.schema}`")

            logger.info("Successfully connected to Databricks")

        except Exception as e:
            logger.error(f"Failed to connect to Databricks: {e}")
            raise

    def close(self) -> None:
        if self.cursor:
            try:
                self.cursor.close()
                logger.debug("Cursor closed")
            except Exception as e:
                logger.warning(f"Error closing cursor: {e}")

        if self.connection:
            try:
                self.connection.close()
                logger.info("Connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[tuple]:
        if not self.cursor:
            raise RuntimeError("Not connected to Databricks. Call connect() first.")

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if self.cursor.description:
                results = self.cursor.fetchall()
                # databricks-sql returns Row objects; normalize to tuples
                normalized = [tuple(r) for r in results]
                logger.debug(f"Query returned {len(normalized)} rows")
                return normalized

            logger.debug("Query executed successfully (no results)")
            return []

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            logger.error(f"Query: {query}")
            raise

    def execute_dict(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.cursor:
            raise RuntimeError("Not connected to Databricks")

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if self.cursor.description:
                columns = [d[0] for d in self.cursor.description]
                rows = self.cursor.fetchall()
                results = [dict(zip(columns, tuple(r))) for r in rows]
                logger.debug(f"Query returned {len(results)} rows")
                return results

            return []

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise

    def execute_many(
        self,
        query: str,
        data: List[tuple],
    ) -> None:
        if not self.cursor:
            raise RuntimeError("Not connected to Databricks")

        try:
            logger.info(f"Executing batch query with {len(data)} rows")
            self.cursor.executemany(query, data)
            logger.info("Batch execution completed")
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise

    def commit(self) -> None:
        # Databricks SQL is autocommit; no-op for interface compatibility
        logger.debug("commit() called — no-op on Databricks SQL (autocommit)")

    def rollback(self) -> None:
        # No client-side transactions on Databricks SQL; statements already applied
        logger.warning(
            "rollback() called — no-op on Databricks SQL. "
            "Statements executed before this point are already committed."
        )

    def get_current_database(self) -> Optional[str]:
        result = self.execute_query("SELECT current_catalog()")
        return result[0][0] if result else None

    def get_current_schema(self) -> Optional[str]:
        result = self.execute_query("SELECT current_schema()")
        return result[0][0] if result else None

    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        schema_name = schema or self.schema
        if not schema_name:
            raise ValueError("Schema must be provided or set in connector")

        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_catalog = ?
              AND table_schema = ?
              AND table_name = ?
        """
        result = self.execute_query(
            query, (self.catalog, schema_name, table_name)
        )
        return result[0][0] > 0 if result else False

    def get_connection_info(self) -> Dict[str, Any]:
        if not self.cursor:
            raise RuntimeError("Not connected to Databricks")

        result = self.execute_query(
            "SELECT current_user(), current_catalog(), current_schema()"
        )

        if result:
            user, catalog, schema = result[0]
            return {
                "platform": self.PLATFORM,
                "user": user,
                "catalog": catalog,
                "schema": schema,
                "server_hostname": self.server_hostname,
                "http_path": self.http_path,
                "connected": True,
            }

        return {"platform": self.PLATFORM, "connected": False}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Error occurred: {exc_val}")
        self.close()
        return False
