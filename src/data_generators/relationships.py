"""
Referential integrity handler for data generation.

Coordinates data generation across dimension and fact tables to ensure
all foreign key relationships are valid.
"""

from typing import Any, Dict, List, Optional, Set

import pandas as pd

from .helpers.base_helper import GeneratedData
from ..utils.logger import get_logger


class ReferentialIntegrityHandler:
    """
    Handles referential integrity between generated datasets.
    
    Validates and ensures all foreign key relationships are valid
    before data loading.
    """
    
    # Define FK relationships: (child_table, child_column, parent_table, parent_column)
    FK_RELATIONSHIPS = [
        # Dimension FKs
        ("dim_customers", "segment_key", "dim_customer_segments", "segment_key"),
        ("dim_products", "category_key", "dim_product_categories", "category_key"),
        ("dim_employees", "store_key", "dim_stores", "store_key"),
        
        # Fact Sales FKs
        ("fact_sales", "date_key", "dim_dates", "date_key"),
        ("fact_sales", "time_key", "dim_time", "time_key"),
        ("fact_sales", "customer_key", "dim_customers", "customer_key"),
        ("fact_sales", "store_key", "dim_stores", "store_key"),
        ("fact_sales", "channel_key", "dim_channels", "channel_key"),
        ("fact_sales", "promotion_key", "dim_promotions", "promotion_key"),
        ("fact_sales", "payment_method_key", "dim_payment_methods", "payment_method_key"),
        ("fact_sales", "shipping_method_key", "dim_shipping_methods", "shipping_method_key"),
        ("fact_sales", "employee_key", "dim_employees", "employee_key"),
        
        # Fact Inventory FKs
        ("fact_inventory_snapshots", "date_key", "dim_dates", "date_key"),
        ("fact_inventory_snapshots", "product_key", "dim_products", "product_key"),
        ("fact_inventory_snapshots", "store_key", "dim_stores", "store_key"),
        
        # Fact Customer Interactions FKs
        ("fact_customer_interactions", "date_key", "dim_dates", "date_key"),
        ("fact_customer_interactions", "time_key", "dim_time", "time_key"),
        ("fact_customer_interactions", "customer_key", "dim_customers", "customer_key"),
        ("fact_customer_interactions", "channel_key", "dim_channels", "channel_key"),
        ("fact_customer_interactions", "store_key", "dim_stores", "store_key"),
        ("fact_customer_interactions", "employee_key", "dim_employees", "employee_key"),
        ("fact_customer_interactions", "sale_key", "fact_sales", "sale_key"),
        
        # Fact Loyalty Points FKs
        ("fact_loyalty_points", "date_key", "dim_dates", "date_key"),
        ("fact_loyalty_points", "time_key", "dim_time", "time_key"),
        ("fact_loyalty_points", "customer_key", "dim_customers", "customer_key"),
        ("fact_loyalty_points", "sale_key", "fact_sales", "sale_key"),
        ("fact_loyalty_points", "channel_key", "dim_channels", "channel_key"),
        
        # Bridge Order Items FKs
        ("bridge_order_items", "sale_key", "fact_sales", "sale_key"),
        ("bridge_order_items", "product_key", "dim_products", "product_key"),
        
        # Bridge Product Promotions FKs
        ("bridge_product_promotions", "product_key", "dim_products", "product_key"),
        ("bridge_product_promotions", "promotion_key", "dim_promotions", "promotion_key"),
    ]
    
    def __init__(self):
        """Initialize handler."""
        self.logger = get_logger("generator.integrity")
        self._validation_errors: List[str] = []
    
    def validate(
        self,
        data: Dict[str, GeneratedData],
        existing_keys: Optional[Dict[str, List[int]]] = None
    ) -> bool:
        """
        Validate referential integrity across all tables.
        
        For incremental generation, pass existing_keys to include pre-existing
        dimension keys in the validation (e.g., from keys cache).
        
        Args:
            data: Dictionary of table_name -> GeneratedData
            existing_keys: Optional dict of table_name -> list of existing keys
            
        Returns:
            True if all FK relationships are valid
        """
        self._validation_errors = []
        existing_keys = existing_keys or {}
        self.logger.info("Validating referential integrity")
        
        for child_table, child_col, parent_table, parent_col in self.FK_RELATIONSHIPS:
            # Skip if child table not in data
            if child_table not in data:
                continue
            
            child_df = data[child_table].data
            
            if child_col not in child_df.columns:
                continue
            
            # Build valid parent keys from:
            # 1. Current batch data (if parent table present)
            # 2. Existing/cached keys (for incremental generation)
            parent_keys: Set[int] = set()
            
            if parent_table in data:
                parent_df = data[parent_table].data
                if parent_col in parent_df.columns:
                    parent_keys.update(parent_df[parent_col].dropna().unique())
            
            # Add existing keys for the parent table
            if parent_table in existing_keys:
                parent_keys.update(existing_keys[parent_table])
            
            # If no parent keys at all, skip validation (can't validate)
            if not parent_keys:
                continue
            
            # Get child keys (excluding nulls for nullable FKs)
            child_keys = set(child_df[child_col].dropna().unique())
            
            # Find orphaned keys
            orphaned = child_keys - parent_keys
            
            if orphaned:
                error_msg = (
                    f"FK violation: {child_table}.{child_col} -> {parent_table}.{parent_col}: "
                    f"{len(orphaned)} orphaned values"
                )
                self._validation_errors.append(error_msg)
                self.logger.warning(error_msg)
        
        is_valid = len(self._validation_errors) == 0
        
        if is_valid:
            self.logger.info("Referential integrity validation passed")
        else:
            self.logger.error(f"Found {len(self._validation_errors)} integrity violations")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors."""
        return self._validation_errors
    
    def get_table_dependencies(self, table_name: str) -> List[str]:
        """
        Get list of tables that this table depends on (parent tables).
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of parent table names
        """
        parents = set()
        for child, _, parent, _ in self.FK_RELATIONSHIPS:
            if child == table_name:
                parents.add(parent)
        return list(parents)
    
    def get_dependent_tables(self, table_name: str) -> List[str]:
        """
        Get list of tables that depend on this table (child tables).
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of child table names
        """
        children = set()
        for child, _, parent, _ in self.FK_RELATIONSHIPS:
            if parent == table_name:
                children.add(child)
        return list(children)
    
    def get_load_order(self) -> List[str]:
        """
        Get table load order that respects FK dependencies.
        
        Returns:
            List of table names in proper load order
        """
        # Tables with no FK dependencies first
        order = [
            # Static dimensions
            "dim_dates",
            "dim_time",
            "dim_channels",
            "dim_payment_methods",
            "dim_shipping_methods",
            "dim_customer_segments",
            "dim_product_categories",
            "dim_promotions",
            "dim_stores",
            # Dimensions with FKs
            "dim_employees",
            "dim_products",
            "dim_customers",
            # Fact tables
            "fact_sales",
            "fact_inventory_snapshots",
            "fact_customer_interactions",
            "fact_loyalty_points",
            # Bridge tables
            "bridge_order_items",
            "bridge_product_promotions",
        ]
        return order
