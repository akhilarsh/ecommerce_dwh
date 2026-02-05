"""
Data loading module for E-Commerce Data Warehouse.

Provides platform-agnostic data loading with support for multiple
data warehouse platforms (Snowflake, Redshift, BigQuery, Databricks).

Usage:
    from src.data_loaders import (
        BaseDataLoader,
        LoaderConfig,
        LoadResult,
        LoadSummary,
        SnowflakeLoader,
        DataLoadOrchestrator,
    )
    
    # Load data into Snowflake
    with SnowflakeConnector() as connector:
        loader = SnowflakeLoader(connector)
        orchestrator = DataLoadOrchestrator(loader)
        summary = orchestrator.load_from_csv_directory("outputs/generated_data/")
"""

from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
    LoadState,
    LoadSummary,
    TableLoadState,
)
from src.data_loaders.snowflake_loader import SnowflakeLoader
from src.data_loaders.load_orchestrator import (
    DataLoadOrchestrator,
    LoadProgress,
)

__all__ = [
    # Base classes
    "BaseDataLoader",
    "LoaderConfig",
    "LoadMethod",
    "LoadResult",
    "LoadState",
    "LoadSummary",
    "TableLoadState",
    # Platform loaders
    "SnowflakeLoader",
    # Orchestration
    "DataLoadOrchestrator",
    "LoadProgress",
]
