"""
Data warehouse connectors package.

Provides a unified interface for connecting to different DWH platforms.

Supported platforms:
- sf / snowflake: Snowflake Data Cloud
- bq / bigquery: Google BigQuery (placeholder)
- rs / redshift: Amazon Redshift (placeholder)
- db / databricks: Databricks (placeholder)

Usage:
    from src.connectors import get_connector
    
    # Using shorthand
    with get_connector("sf") as conn:
        conn.execute_query("SELECT 1")
    
    # Using full name
    with get_connector("snowflake") as conn:
        conn.execute_query("SELECT 1")
"""

from src.connectors.base_connector import BaseConnector
from src.connectors.factory import (
    DEFAULT_DWH,
    get_connector,
    get_dwh_display_name,
    is_dwh_supported,
    list_supported_dwh,
    register_connector,
)
from src.connectors.snowflake_connector import SnowflakeConnector
from src.connectors.postgres_connector import PostgresConnector
from src.connectors.databricks_connector import DatabricksConnector

__all__ = [
    "BaseConnector",
    "SnowflakeConnector",
    "PostgresConnector",
    "DatabricksConnector",
    "get_connector",
    "list_supported_dwh",
    "get_dwh_display_name",
    "is_dwh_supported",
    "register_connector",
    "DEFAULT_DWH",
]
