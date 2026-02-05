"""
Inventory Snapshot Fact Table Model.

Daily inventory levels per product per location.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class FactInventorySnapshots(BaseTable):
    """Inventory snapshot fact table - periodic snapshots of inventory levels."""
    
    table_name = "fact_inventory_snapshots"
    primary_key = ["inventory_snapshot_key"]
    cluster_keys = ["date_key", "product_key"]
    comment = "Daily inventory levels by product and location"
    
    def define_columns(self) -> List[Column]:
        """Define inventory snapshot fact table columns."""
        return [
            Column(
                "inventory_snapshot_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            # Foreign keys to dimensions
            Column(
                "date_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_dates"
            ),
            Column(
                "product_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_products"
            ),
            Column(
                "store_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_stores (NULL for warehouse/online inventory)"
            ),
            # Measures
            Column(
                "quantity_on_hand",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Current inventory quantity"
            ),
            Column(
                "quantity_reserved",
                "NUMBER",
                precision=10,
                default="0",
                comment="Quantity reserved for pending orders"
            ),
            Column(
                "quantity_available",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Available for sale (on_hand - reserved)"
            ),
            Column(
                "reorder_point",
                "NUMBER",
                precision=10,
                comment="Minimum quantity before reorder"
            ),
            Column(
                "is_below_reorder_point",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="True if below reorder point"
            ),
            Column(
                "days_of_supply",
                "NUMBER",
                precision=5,
                scale=1,
                comment="Estimated days until stockout"
            ),
            Column(
                "created_at",
                "TIMESTAMP_NTZ",
                nullable=False,
                comment="Record creation timestamp"
            ),
        ]
    
    foreign_keys = [
        ForeignKey(
            column="date_key",
            reference_table="dim_dates",
            reference_column="date_key"
        ),
        ForeignKey(
            column="product_key",
            reference_table="dim_products",
            reference_column="product_key"
        ),
        ForeignKey(
            column="store_key",
            reference_table="dim_stores",
            reference_column="store_key"
        ),
    ]
