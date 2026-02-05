"""
Data generators for E-Commerce Data Warehouse.

This module provides synthetic test data generation for all dimension
and fact tables with proper referential integrity.

Main entry point: DataGenerator

Usage:
    from src.data_generators import DataGenerator
    
    # Generate initial load
    gen = DataGenerator()
    result = gen.generate_initial()
    gen.save_to_csv(result)
    
    # Daily incremental
    gen.load_keys_from_cache("outputs/keys_cache.json")
    result = gen.generate_incremental(date.today())
"""

# Main entry point
from .generator import DataGenerator, DataGenerationOrchestrator

# Configuration
from .config import (
    DataGenConfig,
    GeneratorConfig,
    VolumesConfig,
    IncrementalConfig,
    load_config,
    get_datagen_config,
)

# Data structures
from .helpers.base_helper import DataGenerationResult, GeneratedData
from .relationships import ReferentialIntegrityHandler

# Keys management
from .utils.keys_loader import ExistingKeysLoader, KeyInfo, TABLE_KEY_COLUMNS

# Utilities
from .utils.customer_selector import CustomerSelector
from .utils.date_keys import (
    date_to_key,
    key_to_date,
    generate_date_keys,
    generate_date_range_keys,
)

# Domain helpers
from .helpers import (
    BaseHelper,
    CalendarHelper,
    CatalogHelper,
    StoreHelper,
    SalesHelper,
    InventoryHelper,
)

# Entity generators
from .entities import (
    BaseEntityGenerator,
    DimDatesGenerator,
    DimTimeGenerator,
    DimChannelsGenerator,
    DimPaymentMethodsGenerator,
    DimShippingMethodsGenerator,
    DimCustomerSegmentsGenerator,
    DimProductCategoriesGenerator,
    DimPromotionsGenerator,
    DimStoresGenerator,
    DimEmployeesGenerator,
    DimProductsGenerator,
    DimCustomersGenerator,
    FactSalesGenerator,
    FactInventorySnapshotsGenerator,
    FactCustomerInteractionsGenerator,
    FactLoyaltyPointsGenerator,
    BridgeOrderItemsGenerator,
    BridgeProductPromotionsGenerator,
)

# Legacy compatibility - incremental orchestrator
# These are now handled by DataGenerator
class IncrementalDataOrchestrator(DataGenerator):
    """Legacy alias for DataGenerator with incremental methods."""
    pass


class GenerationMode:
    """Legacy generation mode constants."""
    INITIAL = "initial"
    DAILY = "daily"
    INVENTORY = "inventory"
    STORE = "store"
    PROMOTION = "promotion"


__all__ = [
    # Main entry point
    "DataGenerator",
    "DataGenerationOrchestrator",
    
    # Configuration
    "DataGenConfig",
    "GeneratorConfig",
    "VolumesConfig",
    "IncrementalConfig",
    "load_config",
    "get_datagen_config",
    
    # Data structures
    "DataGenerationResult",
    "GeneratedData",
    "ReferentialIntegrityHandler",
    
    # Keys management
    "ExistingKeysLoader",
    "KeyInfo",
    "TABLE_KEY_COLUMNS",
    
    # Utilities
    "CustomerSelector",
    "date_to_key",
    "key_to_date",
    "generate_date_keys",
    "generate_date_range_keys",
    
    # Domain helpers
    "BaseHelper",
    "CalendarHelper",
    "CatalogHelper",
    "StoreHelper",
    "SalesHelper",
    "InventoryHelper",
    
    # Entity generators
    "BaseEntityGenerator",
    "DimDatesGenerator",
    "DimTimeGenerator",
    "DimChannelsGenerator",
    "DimPaymentMethodsGenerator",
    "DimShippingMethodsGenerator",
    "DimCustomerSegmentsGenerator",
    "DimProductCategoriesGenerator",
    "DimPromotionsGenerator",
    "DimStoresGenerator",
    "DimEmployeesGenerator",
    "DimProductsGenerator",
    "DimCustomersGenerator",
    "FactSalesGenerator",
    "FactInventorySnapshotsGenerator",
    "FactCustomerInteractionsGenerator",
    "FactLoyaltyPointsGenerator",
    "BridgeOrderItemsGenerator",
    "BridgeProductPromotionsGenerator",
    
    # Legacy compatibility
    "IncrementalDataOrchestrator",
    "IncrementalConfig",
    "GenerationMode",
]
