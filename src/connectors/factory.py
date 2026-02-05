"""
Connector factory for creating DWH connectors based on platform type.

Supported platforms:
- sf / snowflake: Snowflake Data Cloud
- bq / bigquery: Google BigQuery (placeholder)
- rs / redshift: Amazon Redshift (placeholder)
- db / databricks: Databricks (placeholder)
"""

from typing import Dict, Optional, Type

from src.connectors.base_connector import BaseConnector
from src.connectors.snowflake_connector import SnowflakeConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)


# DWH shorthand mapping to connector classes
DWH_REGISTRY: Dict[str, Type[BaseConnector]] = {
    # Snowflake
    "sf": SnowflakeConnector,
    "snowflake": SnowflakeConnector,
    
    # BigQuery (placeholder - implement BigQueryConnector)
    # "bq": BigQueryConnector,
    # "bigquery": BigQueryConnector,
    
    # Redshift (placeholder - implement RedshiftConnector)
    # "rs": RedshiftConnector,
    # "redshift": RedshiftConnector,
    
    # Databricks (placeholder - implement DatabricksConnector)
    # "db": DatabricksConnector,
    # "databricks": DatabricksConnector,
}

# Default DWH platform
DEFAULT_DWH = "snowflake"

# Human-readable names for display
DWH_DISPLAY_NAMES: Dict[str, str] = {
    "sf": "Snowflake",
    "snowflake": "Snowflake",
    "bq": "BigQuery",
    "bigquery": "BigQuery",
    "rs": "Redshift",
    "redshift": "Redshift",
    "db": "Databricks",
    "databricks": "Databricks",
}


def get_connector(dwh: Optional[str] = None, **kwargs) -> BaseConnector:
    """
    Get a connector instance for the specified DWH platform.
    
    Args:
        dwh: DWH shorthand or full name (sf, snowflake, bq, bigquery, etc.)
             Defaults to 'snowflake' if not specified.
        **kwargs: Additional arguments passed to the connector constructor
        
    Returns:
        Configured connector instance
        
    Raises:
        ValueError: If the specified DWH is not supported
        
    Example:
        >>> conn = get_connector("sf")  # Snowflake
        >>> conn = get_connector("bq")  # BigQuery
    """
    platform = (dwh or DEFAULT_DWH).lower().strip()
    
    if platform not in DWH_REGISTRY:
        supported = list_supported_dwh()
        raise ValueError(
            f"Unsupported DWH platform: '{dwh}'. "
            f"Supported platforms: {', '.join(supported)}"
        )
    
    connector_class = DWH_REGISTRY[platform]
    logger.info(f"Creating connector for platform: {DWH_DISPLAY_NAMES.get(platform, platform)}")
    
    return connector_class(**kwargs)


def list_supported_dwh() -> list[str]:
    """
    List all supported DWH platforms.
    
    Returns:
        List of supported platform shorthands
    """
    return sorted(set(DWH_REGISTRY.keys()))


def get_dwh_display_name(dwh: str) -> str:
    """
    Get human-readable display name for a DWH platform.
    
    Args:
        dwh: DWH shorthand or full name
        
    Returns:
        Human-readable platform name
    """
    return DWH_DISPLAY_NAMES.get(dwh.lower(), dwh)


def is_dwh_supported(dwh: str) -> bool:
    """
    Check if a DWH platform is supported.
    
    Args:
        dwh: DWH shorthand or full name
        
    Returns:
        True if the platform is supported
    """
    return dwh.lower() in DWH_REGISTRY


def register_connector(shorthand: str, connector_class: Type[BaseConnector], display_name: Optional[str] = None) -> None:
    """
    Register a new connector class for a DWH platform.
    
    Args:
        shorthand: Short identifier for the platform (e.g., 'sf', 'bq')
        connector_class: Connector class implementing BaseConnector
        display_name: Human-readable name (optional)
        
    Raises:
        TypeError: If connector_class doesn't implement BaseConnector
    """
    if not issubclass(connector_class, BaseConnector):
        raise TypeError(
            f"Connector class must inherit from BaseConnector, got {connector_class}"
        )
    
    DWH_REGISTRY[shorthand.lower()] = connector_class
    
    if display_name:
        DWH_DISPLAY_NAMES[shorthand.lower()] = display_name
    
    logger.info(f"Registered connector: {shorthand} -> {connector_class.__name__}")
