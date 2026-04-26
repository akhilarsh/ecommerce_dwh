"""
Load existing surrogate keys from a data warehouse for incremental data generation.

Works against any connector implementing BaseConnector (Snowflake, PostgreSQL,
Databricks, BigQuery, etc.).

Supports:
- Loading max key values for key sequencing
- Loading valid FK keys for referential integrity
- Caching keys locally for offline generation
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ...utils.logger import get_logger


@dataclass
class KeyInfo:
    """Information about a table's keys."""
    
    table_name: str
    key_column: str
    max_key: int
    valid_keys: List[int] = field(default_factory=list)
    row_count: int = 0
    loaded_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "table_name": self.table_name,
            "key_column": self.key_column,
            "max_key": self.max_key,
            "valid_keys": self.valid_keys,
            "row_count": self.row_count,
            "loaded_at": self.loaded_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeyInfo":
        """Create from dictionary."""
        loaded_at = data.get("loaded_at")
        if isinstance(loaded_at, str):
            loaded_at = datetime.fromisoformat(loaded_at)
        else:
            loaded_at = datetime.now()
        
        return cls(
            table_name=data["table_name"],
            key_column=data["key_column"],
            max_key=data["max_key"],
            valid_keys=data.get("valid_keys", []),
            row_count=data.get("row_count", 0),
            loaded_at=loaded_at,
        )


# Table to primary key column mapping (all 23 tables, in dependency order)
TABLE_KEY_COLUMNS = {
    # Dimension tables (no FK dependencies)
    "dim_dates": "date_key",
    "dim_time": "time_key",
    "dim_channels": "channel_key",
    "dim_payment_methods": "payment_method_key",
    "dim_shipping_methods": "shipping_method_key",
    "dim_customer_segments": "segment_key",
    "dim_loyalty_tiers": "tier_key",
    "dim_product_categories": "category_key",
    "dim_promotions": "promotion_key",
    "dim_accounts": "account_key",
    "dim_stores": "store_key",
    # Dimension tables (with FK dependencies)
    "dim_employees": "employee_key",
    "dim_products": "product_key",
    "dim_customers": "customer_key",
    "dim_customer_address": "address_key",
    "dim_customer_loyalty": "loyalty_key",
    # Fact tables
    "fact_sales": "sale_key",
    "fact_inventory_snapshots": "inventory_snapshot_key",
    "fact_customer_interactions": "interaction_key",
    "fact_loyalty_points": "loyalty_transaction_key",
    # Bridge tables
    "bridge_order_items": "order_item_key",
    "bridge_product_promotions": "product_promotion_key",
    "bridge_account_customers": "account_customer_key",
}


class ExistingKeysLoader:
    """
    Loads existing surrogate keys from the active data warehouse for
    incremental generation.

    Works against any connector implementing BaseConnector — Snowflake,
    PostgreSQL, Databricks, BigQuery, etc. Each platform's qualified-naming
    rules are handled by the connector itself; this loader only emits
    plain `schema.table` references.

    Supports:
    - Loading max key values for key sequencing
    - Loading valid FK keys for referential integrity
    - Caching keys locally for offline generation

    Usage:
        loader = ExistingKeysLoader()
        loader.load_from_warehouse(connector, ["dim_customers"])
        next_key = loader.get_next_key("dim_customers")

        # From cache
        loader = ExistingKeysLoader()
        loader.load_from_cache("keys_cache.json")
    """

    def __init__(self):
        """Initialize the keys loader."""
        self.logger = get_logger("generator.keys_loader")
        self._key_cache: Dict[str, KeyInfo] = {}
        self._loaded_from: Optional[str] = None

    def load_from_warehouse(
        self,
        connector: Any,
        tables: Optional[List[str]] = None,
        schema: str = "ECOMMERCE_DWH",
        load_all_keys: bool = False
    ) -> None:
        """
        Load key information from the active data warehouse.

        Args:
            connector: Active connector instance (any BaseConnector subclass)
            tables: List of tables to load keys for (all if None)
            schema: Schema name (must be qualified for the platform —
                    on BigQuery this should be `project.dataset`)
            load_all_keys: If True, load all valid keys (slower but complete)
        """
        tables_to_load = tables or list(TABLE_KEY_COLUMNS.keys())
        platform = getattr(connector, "PLATFORM", "warehouse")
        self.logger.info(
            f"Loading keys from {platform} for {len(tables_to_load)} tables"
        )
        
        for table_name in tables_to_load:
            key_column = TABLE_KEY_COLUMNS.get(table_name)
            if not key_column:
                self.logger.warning(f"Unknown table: {table_name}, skipping")
                continue
            
            try:
                # Get max key and count
                qualified = _qualify_table(connector, schema, table_name)
                query = f"""
                    SELECT
                        COALESCE(MAX({key_column}), 0) as max_key,
                        COUNT(*) as row_count
                    FROM {qualified}
                """
                result = connector.execute_query(query)
                
                if result:
                    max_key = result[0][0] or 0
                    row_count = result[0][1] or 0
                else:
                    max_key = 0
                    row_count = 0
                
                # Optionally load all valid keys
                valid_keys = []
                if load_all_keys and row_count > 0 and row_count <= 100000:
                    keys_query = f"""
                        SELECT {key_column}
                        FROM {qualified}
                        ORDER BY {key_column}
                    """
                    keys_result = connector.execute_query(keys_query)
                    valid_keys = [row[0] for row in keys_result]
                
                self._key_cache[table_name] = KeyInfo(
                    table_name=table_name,
                    key_column=key_column,
                    max_key=max_key,
                    valid_keys=valid_keys,
                    row_count=row_count,
                )
                
                self.logger.debug(
                    f"{table_name}: max_key={max_key}, count={row_count}"
                )
                
            except Exception as e:
                self.logger.warning(f"Failed to load keys for {table_name}: {e}")
                # Initialize with defaults
                self._key_cache[table_name] = KeyInfo(
                    table_name=table_name,
                    key_column=key_column,
                    max_key=0,
                    row_count=0,
                )
        
        self._loaded_from = platform
        self.logger.info(
            f"Loaded keys for {len(self._key_cache)} tables from {platform}"
        )

    # Back-compat alias for callers still using the old Snowflake-specific name.
    load_from_snowflake = load_from_warehouse
    
    def load_from_cache(self, cache_file: str) -> None:
        """
        Load key information from local cache file.
        
        Args:
            cache_file: Path to JSON cache file
        """
        cache_path = Path(cache_file)
        if not cache_path.exists():
            raise FileNotFoundError(f"Cache file not found: {cache_file}")
        
        self.logger.info(f"Loading keys from cache: {cache_file}")
        
        with open(cache_path, "r") as f:
            data = json.load(f)
        
        self._key_cache = {}
        for table_name, key_data in data.get("tables", {}).items():
            self._key_cache[table_name] = KeyInfo.from_dict(key_data)
        
        self._loaded_from = str(cache_file)
        self.logger.info(f"Loaded keys for {len(self._key_cache)} tables from cache")
    
    def save_to_cache(self, cache_file: str) -> None:
        """
        Save current key information to cache file.
        
        Args:
            cache_file: Path to JSON cache file
        """
        cache_path = Path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "loaded_from": self._loaded_from,
            "tables": {
                name: info.to_dict()
                for name, info in self._key_cache.items()
            }
        }
        
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Saved keys cache to: {cache_file}")
    
    def get_next_key(self, table_name: str) -> int:
        """
        Get next available surrogate key for table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Next surrogate key value (max + 1)
        """
        info = self._key_cache.get(table_name)
        if not info:
            self.logger.warning(f"No key info for {table_name}, returning 1")
            return 1
        
        return info.max_key + 1
    
    def get_max_key(self, table_name: str) -> int:
        """
        Get maximum surrogate key for table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Maximum surrogate key value
        """
        info = self._key_cache.get(table_name)
        return info.max_key if info else 0
    
    def get_valid_fk_keys(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[int]:
        """
        Get valid foreign key values for referential integrity.
        
        Args:
            table_name: Name of the parent table
            filters: Optional filters (not applied to cached keys)
            
        Returns:
            List of valid key values
        """
        info = self._key_cache.get(table_name)
        if not info:
            self.logger.warning(f"No key info for {table_name}")
            return []
        
        # If we have all keys loaded, return them
        if info.valid_keys:
            return info.valid_keys
        
        # Otherwise, generate range from 1 to max_key
        if info.max_key > 0:
            return list(range(1, info.max_key + 1))
        
        return []
    
    def get_row_count(self, table_name: str) -> int:
        """
        Get row count for table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Number of rows
        """
        info = self._key_cache.get(table_name)
        return info.row_count if info else 0
    
    def update_after_generation(
        self,
        table_name: str,
        new_keys: List[int]
    ) -> None:
        """
        Update key cache after generating new records.
        
        Args:
            table_name: Name of the table
            new_keys: List of newly generated keys
        """
        if not new_keys:
            return
        
        info = self._key_cache.get(table_name)
        if info:
            info.max_key = max(info.max_key, max(new_keys))
            info.row_count += len(new_keys)
            # Always update valid_keys - this is important for date/time tables
            # where keys are not sequential integers
            info.valid_keys.extend(new_keys)
        else:
            key_column = TABLE_KEY_COLUMNS.get(table_name, f"{table_name}_key")
            self._key_cache[table_name] = KeyInfo(
                table_name=table_name,
                key_column=key_column,
                max_key=max(new_keys),
                valid_keys=list(new_keys),  # Make a copy
                row_count=len(new_keys),
            )
    
    def get_all_dimension_keys(self) -> Dict[str, List[int]]:
        """
        Get all dimension keys for fact table generation.
        
        Returns:
            Dictionary of dimension table names to key lists
        """
        dimension_tables = [
            "dim_dates", "dim_time", "dim_channels", "dim_payment_methods",
            "dim_shipping_methods", "dim_customer_segments", "dim_loyalty_tiers",
            "dim_product_categories", "dim_promotions", "dim_accounts",
            "dim_stores", "dim_employees", "dim_products",
            "dim_customers", "dim_customer_address", "dim_customer_loyalty",
        ]
        
        result = {}
        for table in dimension_tables:
            keys = self.get_valid_fk_keys(table)
            if keys:
                result[table] = keys
        
        return result
    
    def get_all_keys(self) -> Dict[str, List[int]]:
        """
        Get all keys for all tables (dimensions and facts).
        
        Used for referential integrity validation of incremental data.
        
        Returns:
            Dictionary of table names to key lists
        """
        result = {}
        for table_name, info in self._key_cache.items():
            keys = self.get_valid_fk_keys(table_name)
            if keys:
                result[table_name] = keys
        
        return result
    
    def is_loaded(self) -> bool:
        """Check if keys have been loaded."""
        return len(self._key_cache) > 0
    
    def summary(self) -> Dict[str, Any]:
        """Get summary of loaded keys."""
        return {
            "loaded_from": self._loaded_from,
            "table_count": len(self._key_cache),
            "tables": {
                name: {
                    "max_key": info.max_key,
                    "row_count": info.row_count,
                    "has_all_keys": len(info.valid_keys) > 0,
                }
                for name, info in self._key_cache.items()
            }
        }
    
    def initialize_empty(self) -> None:
        """
        Initialize with empty tables (for initial load scenario).
        
        All tables start with max_key=0, row_count=0.
        """
        self.logger.info("Initializing empty key cache")
        
        for table_name, key_column in TABLE_KEY_COLUMNS.items():
            self._key_cache[table_name] = KeyInfo(
                table_name=table_name,
                key_column=key_column,
                max_key=0,
                valid_keys=[],
                row_count=0,
            )
        
        self._loaded_from = "initialized_empty"
        self.logger.info(f"Initialized {len(self._key_cache)} tables with empty state")



def _qualify_table(connector: Any, schema: str, table_name: str) -> str:
    """
    Build a fully-qualified, platform-correct table reference.

    The keys_loader cannot use plain f"{schema}.{table_name}" because BigQuery
    requires backticks around any identifier with a hyphen (e.g. project ids
    like `ecommerce-db-494418`). Databricks accepts backticks too, and other
    platforms tolerate them in standard SQL.

    Args:
        connector: Active connector — used to read the platform identifier.
        schema:    Schema reference. For BigQuery callers should pass
                   "project.dataset"; for Databricks "catalog.schema"; for
                   Snowflake/PostgreSQL just "schema".
        table_name: Bare table name.

    Returns:
        A SQL fragment usable directly in a FROM clause.
    """
    platform = getattr(connector, "PLATFORM", "")
    if platform == "bigquery":
        # BigQuery: `project.dataset.table` — single backtick pair around
        # the full 3-part name.
        return f"`{schema}.{table_name}`"
    if platform == "databricks":
        # Databricks: `catalog`.`schema`.`table` works, but the keys_loader
        # is given "catalog.schema" as one string — wrap each segment.
        if "." in schema:
            catalog, sch = schema.split(".", 1)
            return f"`{catalog}`.`{sch}`.`{table_name}`"
        return f"`{schema}`.`{table_name}`"
    return f"{schema}.{table_name}"
