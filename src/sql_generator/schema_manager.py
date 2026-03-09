"""
Schema Manager Module.

Orchestrates table creation in proper dependency order.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Type

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.base_table import BaseTable
from src.models.dimension_tables.dim_dates import DimDates
from src.models.dimension_tables.dim_time import DimTime
from src.models.dimension_tables.dim_channels import DimChannels
from src.models.dimension_tables.dim_payment_methods import DimPaymentMethods
from src.models.dimension_tables.dim_shipping_methods import DimShippingMethods
from src.models.dimension_tables.dim_customer_segments import DimCustomerSegments
from src.models.dimension_tables.dim_product_categories import DimProductCategories
from src.models.dimension_tables.dim_promotions import DimPromotions
from src.models.dimension_tables.dim_accounts import DimAccounts
from src.models.dimension_tables.dim_stores import DimStores
from src.models.dimension_tables.dim_employees import DimEmployees
from src.models.dimension_tables.dim_products import DimProducts
from src.models.dimension_tables.dim_customers import DimCustomers
from src.models.fact_tables.fact_sales import FactSales
from src.models.fact_tables.fact_inventory_snapshots import FactInventorySnapshots
from src.models.fact_tables.fact_customer_interactions import FactCustomerInteractions
from src.models.fact_tables.fact_loyalty_points import FactLoyaltyPoints
from src.models.bridge_tables.bridge_order_items import BridgeOrderItems
from src.models.bridge_tables.bridge_product_promotions import BridgeProductPromotions
from src.models.bridge_tables.bridge_account_customers import BridgeAccountCustomers
from src.sql_generator.ddl_generator import DDLGenerator
from src.sql_generator.constraint_generator import ConstraintGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SchemaManager:
    """Manages schema creation and table dependencies."""
    
    def __init__(self):
        """Initialize schema manager."""
        self.ddl_generator = DDLGenerator()
        self.constraint_generator = ConstraintGenerator()
        self.tables_by_category = self._get_tables_by_category()
        self.all_tables = self._get_all_tables_ordered()
    
    def _get_tables_by_category(self) -> Dict[str, List[BaseTable]]:
        """
        Get tables organized by category.
        
        Returns:
            Dictionary of table categories and their instances
        """
        return {
            "static_dimensions": [
                DimDates(),
                DimTime(),
                DimChannels(),
                DimPaymentMethods(),
                DimShippingMethods(),
                DimCustomerSegments(),
                DimProductCategories(),
                DimPromotions(),
                DimAccounts(),
            ],
            "master_dimensions": [
                DimStores(),
                DimProducts(),
                DimCustomers(),
            ],
            "dependent_dimensions": [
                DimEmployees(),  # Depends on dim_stores
            ],
            "fact_tables": [
                FactSales(),
                FactInventorySnapshots(),
                FactCustomerInteractions(),
                FactLoyaltyPoints(),
            ],
            "bridge_tables": [
                BridgeOrderItems(),
                BridgeProductPromotions(),
                BridgeAccountCustomers(),
            ]
        }
    
    def _get_all_tables_ordered(self) -> List[BaseTable]:
        """
        Get all tables in proper dependency order.
        
        Returns:
            List of table instances in creation order
        """
        ordered_tables = []
        categories = self.tables_by_category
        
        # Order matters: static dims -> master dims -> dependent dims -> facts -> bridges
        order = [
            "static_dimensions",
            "master_dimensions",
            "dependent_dimensions",
            "fact_tables",
            "bridge_tables"
        ]
        
        for category in order:
            ordered_tables.extend(categories[category])
        
        logger.debug(f"SchemaManager initialized with {len(ordered_tables)} table definitions")
        return ordered_tables
    
    def get_create_table_scripts(self, table_filter: Optional[str] = None) -> List[str]:
        """
        Generate CREATE TABLE SQL scripts for tables.
        
        Args:
            table_filter: Optional table name to generate only that table's script
        
        Returns:
            List of CREATE TABLE SQL statements
        """
        if table_filter:
            tables = [t for t in self.all_tables if t.table_name.lower() == table_filter.lower()]
            if not tables:
                logger.warning(f"Table '{table_filter}' not found in schema")
                return []
            logger.info(f"Generating CREATE TABLE script for {table_filter}")
        else:
            tables = self.all_tables
            logger.info("Generating CREATE TABLE scripts for all tables")
        
        return self.ddl_generator.generate_create_tables(tables)
    
    def get_drop_table_scripts(self) -> List[str]:
        """
        Generate DROP TABLE SQL scripts for all tables in reverse order.
        
        Returns:
            List of DROP TABLE SQL statements
        """
        logger.info("Generating DROP TABLE scripts for all tables")
        return self.ddl_generator.generate_drop_tables(self.all_tables)
    
    def get_foreign_key_scripts(self, table_filter: Optional[str] = None) -> List[str]:
        """
        Generate ALTER TABLE scripts for foreign keys.
        
        Args:
            table_filter: Optional table name to generate only that table's FK scripts
        
        Returns:
            List of ALTER TABLE SQL statements
        """
        if table_filter:
            tables = [t for t in self.all_tables if t.table_name.lower() == table_filter.lower()]
            if not tables:
                return []
            logger.info(f"Generating foreign key scripts for {table_filter}")
        else:
            tables = self.all_tables
            logger.info("Generating foreign key constraint scripts")
        
        return self.constraint_generator.generate_all_foreign_keys(tables)
    
    def get_all_scripts(self) -> Dict[str, List[str]]:
        """
        Generate all SQL scripts (CREATE, FK).
        
        Returns:
            Dictionary with 'create_tables' and 'foreign_keys' scripts
        """
        return {
            "create_tables": self.get_create_table_scripts(),
            "foreign_keys": self.get_foreign_key_scripts()
        }
    
    def save_all_scripts(self, output_dir: str = "outputs/generated_sql"):
        """
        Save all SQL scripts to files.
        
        Args:
            output_dir: Output directory for SQL files
        """
        import os
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate and save CREATE TABLE scripts
        create_scripts = self.get_create_table_scripts()
        create_file = os.path.join(output_dir, "01_create_tables.sql")
        self.ddl_generator.save_to_file(create_scripts, create_file)
        
        # Generate and save FK scripts
        fk_scripts = self.get_foreign_key_scripts()
        fk_file = os.path.join(output_dir, "02_foreign_keys.sql")
        self.constraint_generator.save_to_file(fk_scripts, fk_file)
        
        # Generate and save DROP TABLE scripts
        drop_scripts = self.get_drop_table_scripts()
        drop_file = os.path.join(output_dir, "00_drop_tables.sql")
        self.ddl_generator.save_to_file(drop_scripts, drop_file)
        
        logger.info(f"All SQL scripts saved to {output_dir}/")
        
        return {
            "drop_tables": drop_file,
            "create_tables": create_file,
            "foreign_keys": fk_file
        }
    
    def get_table_summary(self) -> Dict[str, int]:
        """
        Get summary of table counts by category.
        
        Returns:
            Dictionary with table counts
        """
        summary = {}
        for category, tables in self.tables_by_category.items():
            summary[category] = len(tables)
        summary["total"] = len(self.all_tables)
        
        return summary
