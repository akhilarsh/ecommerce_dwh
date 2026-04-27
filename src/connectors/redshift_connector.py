"""
Amazon Redshift connector with context manager support.

Uses Amazon's official `redshift-connector` driver, which natively understands
SUPER serialization, IAM authentication, and IDP plugins. The wire protocol is
Postgres-compatible, but the driver layer is *not* psycopg2 — it knows about
Redshift-specific syntax (SUPER, IAM identity, GEOGRAPHY) without the workarounds
psycopg2 would require.

Authentication (auto-selected from REDSHIFT_AUTH_METHOD, defaults to 'password'):
  1. Password:
     REDSHIFT_HOST + REDSHIFT_USER + REDSHIFT_PASSWORD
  2. IAM (provisioned cluster):
     REDSHIFT_CLUSTER_IDENTIFIER + REDSHIFT_DB_USER + AWS_REGION
     + standard AWS credential resolution (env / ~/.aws/credentials / instance profile)
  3. IAM (Redshift Serverless):
     REDSHIFT_WORKGROUP_NAME + AWS_REGION
     + standard AWS credential resolution

Always required (regardless of auth method):
    REDSHIFT_DATABASE
Optional:
    REDSHIFT_SCHEMA  (defaults to "ecommerce_dwh")
    REDSHIFT_PORT    (defaults to 5439)
"""

import os
from typing import Any, Dict, List, Optional, Union

from src.connectors.base_connector import BaseConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedshiftConnector(BaseConnector):
    """
    Amazon Redshift connection manager.

    Supports both provisioned clusters and Redshift Serverless workgroups via
    the same connector. Provisioned vs Serverless is auto-detected from which
    env var is set.

    Usage:
        with RedshiftConnector() as conn:
            conn.execute_query("SELECT 1")
    """

    PLATFORM = "redshift"

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: Optional[str] = None,
        cluster_identifier: Optional[str] = None,
        workgroup_name: Optional[str] = None,
        db_user: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.host = host or os.getenv("REDSHIFT_HOST")
        self.port = int(port or os.getenv("REDSHIFT_PORT", "5439"))
        self.database = database or os.getenv("REDSHIFT_DATABASE")
        self.schema = schema or os.getenv("REDSHIFT_SCHEMA", "ecommerce_dwh")

        self.user = user or os.getenv("REDSHIFT_USER")
        self.password = password or os.getenv("REDSHIFT_PASSWORD")

        self.cluster_identifier = cluster_identifier or os.getenv(
            "REDSHIFT_CLUSTER_IDENTIFIER"
        )
        self.workgroup_name = workgroup_name or os.getenv("REDSHIFT_WORKGROUP_NAME")
        self.db_user = db_user or os.getenv("REDSHIFT_DB_USER")
        self.region = region or os.getenv("AWS_REGION")

        self.auth_method = (
            auth_method or os.getenv("REDSHIFT_AUTH_METHOD", "password")
        ).lower().strip()

        self.connection = None
        self.cursor = None

        self._validate_config()

    def _validate_config(self) -> None:
        if not self.database:
            raise ValueError(
                "Missing required Redshift parameter: database. "
                "Set REDSHIFT_DATABASE."
            )

        if self.auth_method == "password":
            missing = []
            if not self.host:
                missing.append("host")
            if not self.user:
                missing.append("user")
            if not self.password:
                missing.append("password")
            if missing:
                raise ValueError(
                    f"Missing required Redshift password-auth parameters: "
                    f"{', '.join(missing)}. Set REDSHIFT_HOST, REDSHIFT_USER, "
                    "REDSHIFT_PASSWORD."
                )
        elif self.auth_method == "iam":
            # IAM auth needs either a cluster_identifier (provisioned) or a
            # workgroup_name (serverless). Region must be set for STS.
            if not self.cluster_identifier and not self.workgroup_name:
                raise ValueError(
                    "Missing Redshift IAM-auth target: set REDSHIFT_CLUSTER_IDENTIFIER "
                    "(provisioned) or REDSHIFT_WORKGROUP_NAME (serverless)."
                )
            if not self.region:
                raise ValueError(
                    "Missing AWS_REGION for Redshift IAM auth."
                )
            if self.cluster_identifier and not self.db_user:
                raise ValueError(
                    "Missing REDSHIFT_DB_USER for Redshift IAM auth on a "
                    "provisioned cluster."
                )
        else:
            raise ValueError(
                f"Unsupported REDSHIFT_AUTH_METHOD '{self.auth_method}'. "
                "Use 'password' or 'iam'."
            )

    def connect(self) -> None:
        import redshift_connector

        try:
            target = (
                self.cluster_identifier
                or self.workgroup_name
                or self.host
                or "<unknown>"
            )
            logger.info(
                f"Connecting to Redshift: {target} "
                f"(database={self.database}, schema={self.schema}, "
                f"auth={self.auth_method})"
            )

            connect_kwargs: Dict[str, Any] = {
                "database": self.database,
                "port": self.port,
            }

            if self.auth_method == "password":
                connect_kwargs.update(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                )
            else:  # iam
                connect_kwargs["iam"] = True
                connect_kwargs["region"] = self.region
                if self.cluster_identifier:
                    connect_kwargs["cluster_identifier"] = self.cluster_identifier
                    if self.db_user:
                        connect_kwargs["db_user"] = self.db_user
                if self.workgroup_name:
                    # Serverless: workgroup endpoints are derivable from the
                    # workgroup name; the driver fetches the host via the
                    # redshift-serverless API using the supplied region + creds.
                    connect_kwargs["is_serverless"] = True
                    connect_kwargs["workgroup_name"] = self.workgroup_name

            self.connection = redshift_connector.connect(**connect_kwargs)
            self.connection.autocommit = False
            self.cursor = self.connection.cursor()

            if self.schema:
                # Postgres-compatible search_path. Quote-safe via parameter binding
                # is not applicable to identifiers; use a defensive identifier
                # check (alphanumeric + underscore) before interpolation.
                if not self._is_safe_identifier(self.schema):
                    raise ValueError(
                        f"Refusing to use unsafe schema name: {self.schema!r}"
                    )
                self.cursor.execute(
                    f'SET search_path TO "{self.schema}", public'
                )

            logger.info("Successfully connected to Redshift")

        except Exception as e:
            logger.error(f"Failed to connect to Redshift: {e}")
            raise

    @staticmethod
    def _is_safe_identifier(name: str) -> bool:
        return name.replace("_", "").isalnum()

    def close(self) -> None:
        if self.cursor:
            try:
                self.cursor.close()
                logger.debug("Cursor closed")
            except Exception as e:
                logger.warning(f"Error closing cursor: {e}")
            finally:
                self.cursor = None

        if self.connection:
            try:
                self.connection.close()
                logger.info("Connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self.connection = None

    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[tuple]:
        if not self.cursor:
            raise RuntimeError("Not connected to Redshift. Call connect() first.")

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if self.cursor.description:
                results = self.cursor.fetchall()
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
            raise RuntimeError("Not connected to Redshift")

        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if self.cursor.description:
                columns = [d[0] for d in self.cursor.description]
                rows = self.cursor.fetchall()
                return [dict(zip(columns, tuple(r))) for r in rows]

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
            raise RuntimeError("Not connected to Redshift")

        try:
            logger.info(f"Executing batch query with {len(data)} rows")
            self.cursor.executemany(query, data)
            logger.info("Batch execution completed")
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()
            logger.debug("Transaction committed")

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
            logger.debug("Transaction rolled back")

    def get_current_database(self) -> Optional[str]:
        result = self.execute_query("SELECT current_database()")
        return result[0][0] if result else None

    def get_current_schema(self) -> Optional[str]:
        result = self.execute_query("SELECT current_schema()")
        return result[0][0] if result else None

    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        schema_name = schema or self.schema
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        """
        result = self.execute_query(query, (schema_name, table_name))
        return result[0][0] > 0 if result else False

    def get_connection_info(self) -> Dict[str, Any]:
        if not self.cursor:
            raise RuntimeError("Not connected to Redshift")

        result = self.execute_query(
            "SELECT current_user, current_database(), current_schema()"
        )

        if result:
            user, database, schema = result[0]
            info: Dict[str, Any] = {
                "platform": self.PLATFORM,
                "user": user,
                "database": database,
                "schema": schema,
                "host": self.host,
                "port": self.port,
                "auth_method": self.auth_method,
                "connected": True,
            }
            if self.cluster_identifier:
                info["cluster"] = self.cluster_identifier
            if self.workgroup_name:
                info["cluster"] = f"{self.workgroup_name} (serverless)"
            return info

        return {"platform": self.PLATFORM, "connected": False}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Error occurred: {exc_val}")
            try:
                self.rollback()
            except Exception:
                pass
        self.close()
        return False
