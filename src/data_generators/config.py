"""
Configuration management for data generation.

Single source of truth: datagen_config.yaml
Environment variables and CLI args can override YAML values.

Priority (highest to lowest):
1. CLI arguments
2. Environment variables (DATAGEN_* prefix)
3. datagen_config.yaml
"""

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..utils.logger import get_logger


# =============================================================================
# Config dataclasses - these define structure, YAML provides values
# =============================================================================

@dataclass
class VolumesConfig:
    """Volume settings for initial data generation."""
    customers: int = 0
    products: int = 0
    stores: int = 0
    employees: int = 0
    promotions: int = 0
    channels: int = 0
    payment_methods: int = 0
    shipping_methods: int = 0
    customer_segments: int = 0
    product_categories: int = 0
    sales: int = 0
    inventory_snapshots: int = 0
    customer_interactions: int = 0
    loyalty_transactions: int = 0


@dataclass
class IncrementalConfig:
    """Settings for all incremental generation (daily, store opening, promotions)."""
    # Date range for incremental data
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    # Volume counts (distributed across date range)
    new_customers: int = 0
    new_orders: int = 0
    new_interactions: int = 0
    new_loyalty_transactions: int = 0
    min_items_per_order: int = 1
    max_items_per_order: int = 5
    existing_customer_ratio: float = 0.8
    # Store opening
    employees_per_store: int = 5
    include_initial_inventory: bool = True
    # Promotion campaigns
    discount_min: float = 0.10
    discount_max: float = 0.30




@dataclass
class DatesConfig:
    """Date range settings."""
    start: Optional[date] = None
    end: Optional[date] = None


@dataclass
class PathsConfig:
    """Output path settings."""
    output_dir: str = ""
    incremental_output_dir: str = ""
    keys_cache: str = ""


@dataclass
class SettingsConfig:
    """General settings."""
    seed: Optional[int] = None
    validate_integrity: bool = True
    locale: str = "en_US"


@dataclass
class DataGenConfig:
    """Complete data generation configuration."""
    volumes: VolumesConfig = field(default_factory=VolumesConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)
    dates: DatesConfig = field(default_factory=DatesConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    settings: SettingsConfig = field(default_factory=SettingsConfig)
    


# =============================================================================
# YAML parsing - reads values from datagen_config.yaml
# =============================================================================

def _parse_date(value: Any) -> Optional[date]:
    """Parse date from string or date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None


def _parse_volumes(data: Dict[str, Any]) -> VolumesConfig:
    """Parse volumes from YAML data."""
    # Support both 'initial_load' and 'volumes' keys
    section = data.get("initial_load", data.get("volumes", {}))
    return VolumesConfig(
        customers=section.get("customers", 0),
        products=section.get("products", 0),
        stores=section.get("stores", 0),
        employees=section.get("employees", 0),
        promotions=section.get("promotions", 0),
        channels=section.get("channels", 0),
        payment_methods=section.get("payment_methods", 0),
        shipping_methods=section.get("shipping_methods", 0),
        customer_segments=section.get("customer_segments", 0),
        product_categories=section.get("product_categories", 0),
        sales=section.get("sales", 0),
        inventory_snapshots=section.get("inventory_snapshots", 0),
        customer_interactions=section.get("customer_interactions", 0),
        loyalty_transactions=section.get("loyalty_transactions", 0),
    )


def _parse_incremental(data: Dict[str, Any]) -> IncrementalConfig:
    """Parse incremental config from YAML data."""
    section = data.get("incremental", {})
    # Also support legacy separate sections
    daily = data.get("daily", {})
    store_opening = data.get("store_opening", {})
    promotions = data.get("promotions", {})
    
    return IncrementalConfig(
        # Date range
        start_date=_parse_date(section.get("start_date")),
        end_date=_parse_date(section.get("end_date")),
        # Volume counts
        new_customers=section.get("new_customers", daily.get("new_customers", 0)),
        new_orders=section.get("new_orders", daily.get("new_orders", 0)),
        new_interactions=section.get("new_interactions", daily.get("new_interactions", 0)),
        new_loyalty_transactions=section.get("new_loyalty_transactions", daily.get("new_loyalty_transactions", 0)),
        min_items_per_order=section.get("min_items_per_order", daily.get("min_items_per_order", 1)),
        max_items_per_order=section.get("max_items_per_order", daily.get("max_items_per_order", 5)),
        existing_customer_ratio=section.get("existing_customer_ratio", daily.get("existing_customer_ratio", 0.8)),
        # Store opening
        employees_per_store=section.get("employees_per_store", store_opening.get("employees_per_store", 5)),
        include_initial_inventory=section.get("include_initial_inventory", store_opening.get("include_initial_inventory", True)),
        # Promotions
        discount_min=section.get("discount_min", promotions.get("discount_min", 0.10)),
        discount_max=section.get("discount_max", promotions.get("discount_max", 0.30)),
    )


def _parse_dates(data: Dict[str, Any]) -> DatesConfig:
    """Parse dates config from YAML data."""
    # Check both 'dates' section and 'initial_load' for backwards compat
    dates_section = data.get("dates", {})
    initial_load = data.get("initial_load", {})
    
    start = _parse_date(dates_section.get("start") or initial_load.get("date_start"))
    end = _parse_date(dates_section.get("end") or initial_load.get("date_end"))
    
    return DatesConfig(start=start, end=end)


def _parse_paths(data: Dict[str, Any]) -> PathsConfig:
    """Parse paths config from YAML data."""
    section = data.get("paths", {})
    return PathsConfig(
        output_dir=section.get("output_dir", ""),
        incremental_output_dir=section.get("incremental_output_dir", ""),
        keys_cache=section.get("keys_cache", ""),
    )


def _parse_settings(data: Dict[str, Any]) -> SettingsConfig:
    """Parse settings config from YAML data."""
    section = data.get("settings", {})
    return SettingsConfig(
        seed=section.get("seed"),
        validate_integrity=section.get("validate_integrity", True),
        locale=section.get("locale", "en_US"),
    )


def _config_from_yaml(data: Dict[str, Any]) -> DataGenConfig:
    """Create DataGenConfig from parsed YAML dictionary."""
    return DataGenConfig(
        volumes=_parse_volumes(data),
        incremental=_parse_incremental(data),
        dates=_parse_dates(data),
        paths=_parse_paths(data),
        settings=_parse_settings(data),
    )


# =============================================================================
# Environment variable overrides
# =============================================================================

ENV_MAPPINGS = {
    # Volumes
    "DATAGEN_CUSTOMERS": ("volumes", "customers", int),
    "DATAGEN_PRODUCTS": ("volumes", "products", int),
    "DATAGEN_STORES": ("volumes", "stores", int),
    "DATAGEN_EMPLOYEES": ("volumes", "employees", int),
    "DATAGEN_PROMOTIONS": ("volumes", "promotions", int),
    "DATAGEN_SALES": ("volumes", "sales", int),
    "DATAGEN_INVENTORY_SNAPSHOTS": ("volumes", "inventory_snapshots", int),
    "DATAGEN_CUSTOMER_INTERACTIONS": ("volumes", "customer_interactions", int),
    "DATAGEN_LOYALTY_TRANSACTIONS": ("volumes", "loyalty_transactions", int),
    # Incremental
    "DATAGEN_NEW_CUSTOMERS": ("incremental", "new_customers", int),
    "DATAGEN_NEW_ORDERS": ("incremental", "new_orders", int),
    "DATAGEN_NEW_INTERACTIONS": ("incremental", "new_interactions", int),
    "DATAGEN_NEW_LOYALTY": ("incremental", "new_loyalty_transactions", int),
    "DATAGEN_EXISTING_CUSTOMER_RATIO": ("incremental", "existing_customer_ratio", float),
    "DATAGEN_EMPLOYEES_PER_STORE": ("incremental", "employees_per_store", int),
    "DATAGEN_DISCOUNT_MIN": ("incremental", "discount_min", float),
    "DATAGEN_DISCOUNT_MAX": ("incremental", "discount_max", float),
    # Settings
    "DATAGEN_SEED": ("settings", "seed", int),
    # Paths
    "DATAGEN_OUTPUT_DIR": ("paths", "output_dir", str),
    "DATAGEN_INCREMENTAL_OUTPUT_DIR": ("paths", "incremental_output_dir", str),
    "DATAGEN_KEYS_CACHE": ("paths", "keys_cache", str),
}


def _apply_env_overrides(config: DataGenConfig) -> DataGenConfig:
    """Apply environment variable overrides to config."""
    for env_var, (section, attr, converter) in ENV_MAPPINGS.items():
        value = os.getenv(env_var)
        if value is not None:
            section_obj = getattr(config, section)
            try:
                setattr(section_obj, attr, converter(value))
            except (ValueError, TypeError):
                pass  # Skip invalid values
    return config


# =============================================================================
# Main config loader
# =============================================================================

def load_config(config_path: Optional[str] = None) -> DataGenConfig:
    """
    Load configuration from datagen_config.yaml with environment overrides.
    
    Args:
        config_path: Optional path to YAML config file.
                    Defaults to src/data_generators/datagen_config.yaml
    
    Returns:
        DataGenConfig populated from YAML
    
    Raises:
        FileNotFoundError: If config file doesn't exist and no path provided
    """
    logger = get_logger("generator.config")
    
    # Determine config path
    if config_path is None:
        yaml_path = Path(__file__).parent / "datagen_config.yaml"
    else:
        yaml_path = Path(config_path)
    
    # Load from YAML - this is the source of truth
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {yaml_path}\n"
            f"datagen_config.yaml is required - it is the single source of truth."
        )
    
    logger.debug(f"Loading config from: {yaml_path}")
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f) or {}
    
    config = _config_from_yaml(data)
    
    # Apply environment variable overrides
    config = _apply_env_overrides(config)
    
    return config


def get_datagen_config(config_path: Optional[str] = None) -> DataGenConfig:
    """Alias for load_config (backwards compatibility)."""
    return load_config(config_path)


# =============================================================================
# Legacy compatibility
# =============================================================================

@dataclass
class GeneratorConfig:
    """Legacy configuration class - use DataGenConfig instead."""
    
    seed: Optional[int] = None
    num_customers: int = 0
    num_products: int = 0
    num_sales: int = 0
    num_stores: int = 0
    num_employees: int = 0
    num_promotions: int = 0
    num_inventory_snapshots: int = 0
    num_customer_interactions: int = 0
    num_loyalty_transactions: int = 0
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    
    @classmethod
    def from_datagen_config(cls, config: DataGenConfig) -> "GeneratorConfig":
        """Create GeneratorConfig from DataGenConfig."""
        return cls(
            seed=config.settings.seed,
            num_customers=config.volumes.customers,
            num_products=config.volumes.products,
            num_sales=config.volumes.sales,
            num_stores=config.volumes.stores,
            num_employees=config.volumes.employees,
            num_promotions=config.volumes.promotions,
            num_inventory_snapshots=config.volumes.inventory_snapshots,
            num_customer_interactions=config.volumes.customer_interactions,
            num_loyalty_transactions=config.volumes.loyalty_transactions,
            date_start=config.dates.start,
            date_end=config.dates.end,
        )
    
    def to_datagen_config(self) -> DataGenConfig:
        """Convert to DataGenConfig."""
        config = DataGenConfig()
        config.settings.seed = self.seed
        config.volumes.customers = self.num_customers
        config.volumes.products = self.num_products
        config.volumes.sales = self.num_sales
        config.volumes.stores = self.num_stores
        config.volumes.employees = self.num_employees
        config.volumes.promotions = self.num_promotions
        config.volumes.inventory_snapshots = self.num_inventory_snapshots
        config.volumes.customer_interactions = self.num_customer_interactions
        config.volumes.loyalty_transactions = self.num_loyalty_transactions
        config.dates.start = self.date_start
        config.dates.end = self.date_end
        return config
