"""
Configuration management for data generation.

Single source of truth: datagen_config.yaml
Environment variables and CLI args can override YAML values.

Priority (highest to lowest):
1. CLI arguments
2. Environment variables (via ${VAR || default} syntax in YAML)
3. Default values in YAML

The YAML file supports environment variable substitution:
  ${ENV_VAR || default_value}
  - If ENV_VAR is set in environment, its value is used
  - Otherwise, default_value is used
"""

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..utils.logger import get_logger


# =============================================================================
# Environment variable substitution in YAML values
# =============================================================================

# Pattern to match ${ENV_VAR || default_value}
ENV_PATTERN = re.compile(r'\$\{([^}|]+)\s*\|\|\s*([^}]+)\}')


def _substitute_env_vars(value: Any) -> Any:
    """
    Substitute environment variables in a value.
    
    Supports format: ${ENV_VAR || default_value}
    - If ENV_VAR is set, returns its value
    - Otherwise, returns default_value
    
    Args:
        value: Value to process (string, dict, list, or other)
        
    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        match = ENV_PATTERN.match(value.strip())
        if match:
            env_var = match.group(1).strip()
            default = match.group(2).strip()
            return os.getenv(env_var, default)
        return value
    elif isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_env_vars(item) for item in value]
    return value


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
    # Customer exclusion - these customers won't receive new orders
    excluded_customer_keys: Optional[List[int]] = None
    # Random exclusion - randomly exclude N existing customers from new orders
    exclude_random_customers: int = 0
    # Frequent shoppers - guarantee some customers get multiple orders
    frequent_shopper_count: int = 0
    frequent_shopper_min_orders: int = 2
    frequent_shopper_max_orders: int = 5
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


def _parse_int(value: Any, default: int = 0) -> int:
    """Parse integer from string or number."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_float(value: Any, default: float = 0.0) -> float:
    """Parse float from string or number."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Parse boolean from string or bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return default


def _parse_volumes(data: Dict[str, Any]) -> VolumesConfig:
    """Parse volumes from YAML data."""
    # Support both 'initial_load' and 'volumes' keys
    section = data.get("initial_load", data.get("volumes", {}))
    return VolumesConfig(
        customers=_parse_int(section.get("customers"), 0),
        products=_parse_int(section.get("products"), 0),
        stores=_parse_int(section.get("stores"), 0),
        employees=_parse_int(section.get("employees"), 0),
        promotions=_parse_int(section.get("promotions"), 0),
        channels=_parse_int(section.get("channels"), 0),
        payment_methods=_parse_int(section.get("payment_methods"), 0),
        shipping_methods=_parse_int(section.get("shipping_methods"), 0),
        customer_segments=_parse_int(section.get("customer_segments"), 0),
        product_categories=_parse_int(section.get("product_categories"), 0),
        sales=_parse_int(section.get("sales"), 0),
        inventory_snapshots=_parse_int(section.get("inventory_snapshots"), 0),
        customer_interactions=_parse_int(section.get("customer_interactions"), 0),
        loyalty_transactions=_parse_int(section.get("loyalty_transactions"), 0),
    )


def _parse_int_list(value: Any) -> Optional[List[int]]:
    """Parse a list of integers from string or list."""
    if value is None:
        return None
    if isinstance(value, list):
        return [_parse_int(v, 0) for v in value]
    if isinstance(value, str):
        # Support comma-separated string: "1,2,3" or "1, 2, 3"
        if not value.strip():
            return None
        return [_parse_int(v.strip(), 0) for v in value.split(",") if v.strip()]
    return None


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
        new_customers=_parse_int(section.get("new_customers") or daily.get("new_customers"), 0),
        new_orders=_parse_int(section.get("new_orders") or daily.get("new_orders"), 0),
        new_interactions=_parse_int(section.get("new_interactions") or daily.get("new_interactions"), 0),
        new_loyalty_transactions=_parse_int(section.get("new_loyalty_transactions") or daily.get("new_loyalty_transactions"), 0),
        min_items_per_order=_parse_int(section.get("min_items_per_order") or daily.get("min_items_per_order"), 1),
        max_items_per_order=_parse_int(section.get("max_items_per_order") or daily.get("max_items_per_order"), 5),
        existing_customer_ratio=_parse_float(section.get("existing_customer_ratio") or daily.get("existing_customer_ratio"), 0.8),
        # Customer exclusion
        excluded_customer_keys=_parse_int_list(section.get("excluded_customer_keys")),
        exclude_random_customers=_parse_int(section.get("exclude_random_customers"), 0),
        # Frequent shoppers
        frequent_shopper_count=_parse_int(section.get("frequent_shopper_count"), 0),
        frequent_shopper_min_orders=_parse_int(section.get("frequent_shopper_min_orders"), 2),
        frequent_shopper_max_orders=_parse_int(section.get("frequent_shopper_max_orders"), 5),
        # Store opening
        employees_per_store=_parse_int(section.get("employees_per_store") or store_opening.get("employees_per_store"), 5),
        include_initial_inventory=_parse_bool(section.get("include_initial_inventory") if section.get("include_initial_inventory") is not None else store_opening.get("include_initial_inventory"), True),
        # Promotions
        discount_min=_parse_float(section.get("discount_min") or promotions.get("discount_min"), 0.10),
        discount_max=_parse_float(section.get("discount_max") or promotions.get("discount_max"), 0.30),
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
        output_dir=str(section.get("output_dir", "") or ""),
        incremental_output_dir=str(section.get("incremental_output_dir", "") or ""),
        keys_cache=str(section.get("keys_cache", "") or ""),
    )


def _parse_settings(data: Dict[str, Any]) -> SettingsConfig:
    """Parse settings config from YAML data."""
    section = data.get("settings", {})
    seed_val = section.get("seed")
    seed = _parse_int(seed_val, None) if seed_val is not None else None
    return SettingsConfig(
        seed=seed,
        validate_integrity=_parse_bool(section.get("validate_integrity"), True),
        locale=str(section.get("locale", "en_US") or "en_US"),
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
# Main config loader
# =============================================================================

def load_config(config_path: Optional[str] = None) -> DataGenConfig:
    """
    Load configuration from datagen_config.yaml with environment variable substitution.
    
    The YAML file supports ${ENV_VAR || default} syntax for environment variables.
    
    Args:
        config_path: Optional path to YAML config file.
                    Defaults to src/data_generators/datagen_config.yaml
    
    Returns:
        DataGenConfig populated from YAML with env vars substituted
    
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
    
    # Substitute environment variables in YAML values
    data = _substitute_env_vars(data)
    
    config = _config_from_yaml(data)
    
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
