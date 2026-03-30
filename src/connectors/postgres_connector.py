"""
PostgreSQL database connector with context manager support.

Reads connection parameters from environment variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD,
    POSTGRES_DATABASE, POSTGRES_SCHEMA
"""

import os
from typing import Any, Dict, List, Optional, Union

import psycopg2
import psycopg2.extras
import psycopg2.sql as sql

from src.connectors.base_connector import BaseConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostgresConnector(BaseConnector):
    """
    PostgreSQL connection manager with context manager support.

    Usage:
        with PostgresConnector() as conn:
            conn.execute_query("SELECT 1")
    """

    PLATFORM = "postgres"

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(port or os.getenv("POSTGRES_PORT", "5432"))
        self.user = user or os.getenv("POSTGRES_USER")
        self.password = password or os.getenv("POSTGRES_PASSWORD")
        self.database = database or os.getenv("POSTGRES_DATABASE")
        self.schema = schema or os.getenv("POSTGRES_SCHEMA", "public")

        self.connection: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None

        self._validate_config()

    def _validate_config(self) -> None:
        required = {"user": self.user, "database": self.database}
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(
                f"Missing required PostgreSQL parameters: {', '.join(missing)}. "
                "Set POSTGRES_USER and POSTGRES_DATABASE environment variables."
            )

    def connect(self) -> None:
        try:
            logger.info(
                f"Connecting to PostgreSQL: {self.host}:{self.port}/{self.database}"
            )

            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                dbname=self.database,
            )
            self.connection.autocommit = False
            self.cursor = self.connection.cursor()

            if self.schema and self.schema != "public":
                stmt = sql.SQL("SET search_path TO {schema}, public").format(
                    schema=sql.Identifier(self.schema)
                )
                self.cursor.execute(stmt)

            logger.info("Successfully connected to PostgreSQL")

        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
            logger.debug("Cursor closed")

        if self.connection:
            self.connection.close()
            logger.info("Connection closed")

    def execute_query(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[tuple]:
        if not self.cursor:
            raise RuntimeError("Not connected to PostgreSQL. Call connect() first.")

        try:
            logger.debug(f"Executing query: {query[:100]}...")

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if self.cursor.description:
                results = self.cursor.fetchall()
                logger.debug(f"Query returned {len(results)} rows")
                return results

            logger.debug("Query executed successfully (no results)")
            return []

        except psycopg2.Error as e:
            logger.error(f"SQL execution failed: {e}")
            logger.error(f"Query: {query}")
            raise

    def execute_dict(
        self,
        query: str,
        params: Optional[Union[tuple, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.connection:
            raise RuntimeError("Not connected to PostgreSQL")

        try:
            cursor = self.connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.debug(f"Executing query: {query[:100]}...")

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if cursor.description:
                results = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Query returned {len(results)} rows")
                cursor.close()
                return results

            cursor.close()
            return []

        except psycopg2.Error as e:
            logger.error(f"SQL execution failed: {e}")
            raise

    def execute_many(
        self,
        query: str,
        data: List[tuple],
    ) -> None:
        if not self.cursor:
            raise RuntimeError("Not connected to PostgreSQL")

        try:
            logger.info(f"Executing batch query with {len(data)} rows")
            psycopg2.extras.execute_values(
                self.cursor,
                query,
                data,
                page_size=1000,
            )
            logger.info("Batch execution completed")

        except psycopg2.Error as e:
            logger.error(f"Batch execution failed: {e}")
            raise

    def commit(self) -> None:
        if not self.connection:
            raise RuntimeError("Not connected to PostgreSQL")

        self.connection.commit()
        logger.debug("Transaction committed")

    def rollback(self) -> None:
        if not self.connection:
            raise RuntimeError("Not connected to PostgreSQL")

        self.connection.rollback()
        logger.warning("Transaction rolled back")

    def get_current_database(self) -> Optional[str]:
        result = self.execute_query("SELECT current_database()")
        return result[0][0] if result else None

    def get_current_schema(self) -> Optional[str]:
        result = self.execute_query("SELECT current_schema()")
        return result[0][0] if result else None

    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        schema_name = schema or self.schema or "public"
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
            raise RuntimeError("Not connected to PostgreSQL")

        result = self.execute_query("""
            SELECT
                current_user,
                current_database(),
                current_schema(),
                inet_server_addr(),
                inet_server_port()
        """)

        if result:
            user, database, schema, host, port = result[0]
            return {
                "platform": self.PLATFORM,
                "user": user,
                "database": database,
                "schema": schema,
                "host": str(host) if host else self.host,
                "port": port or self.port,
                "connected": True,
            }

        return {"platform": self.PLATFORM, "connected": False}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Error occurred: {exc_val}")
            if self.connection:
                self.rollback()

        self.close()
        return False
