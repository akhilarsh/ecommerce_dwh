"""
Loader factory for creating data loaders based on connector platform.

Returns the correct BaseDataLoader implementation for the given connector.
"""

from typing import Optional

from src.connectors.base_connector import BaseConnector
from src.data_loaders.base_loader import BaseDataLoader, LoaderConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_loader(
    connector: BaseConnector,
    config: Optional[LoaderConfig] = None,
) -> BaseDataLoader:
    """
    Get a data loader instance for the given connector's platform.

    Args:
        connector: Connected BaseConnector instance
        config: Optional loader configuration

    Returns:
        Platform-specific data loader

    Raises:
        ValueError: If no loader exists for the connector's platform
    """
    platform = connector.PLATFORM

    if platform == "snowflake":
        from src.data_loaders.snowflake_loader import SnowflakeLoader
        logger.info("Creating Snowflake data loader")
        return SnowflakeLoader(connector, config)

    if platform == "postgres":
        from src.data_loaders.postgres_loader import PostgresLoader
        logger.info("Creating PostgreSQL data loader")
        return PostgresLoader(connector, config)

    if platform == "databricks":
        from src.data_loaders.databricks_loader import DatabricksLoader
        logger.info("Creating Databricks data loader")
        return DatabricksLoader(connector, config)

    if platform == "bigquery":
        from src.data_loaders.bigquery_loader import BigQueryLoader
        logger.info("Creating BigQuery data loader")
        return BigQueryLoader(connector, config)

    if platform == "redshift":
        from src.data_loaders.redshift_loader import RedshiftLoader
        logger.info("Creating Redshift data loader")
        return RedshiftLoader(connector, config)

    raise ValueError(
        f"No data loader available for platform: '{platform}'. "
        f"Supported: snowflake, postgres, databricks, bigquery, redshift"
    )
