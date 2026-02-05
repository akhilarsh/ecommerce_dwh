"""
Product Dimension Table Model.

Product catalog with SCD Type 2 for tracking history of product changes.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class DimProducts(BaseTable):
    """Product dimension with SCD Type 2."""
    
    table_name = "dim_products"
    primary_key = ["product_key"]
    comment = "Product catalog with historical tracking (SCD Type 2)"
    
    def define_columns(self) -> List[Column]:
        """Define product dimension columns."""
        return [
            Column(
                "product_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "product_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business product identifier (natural key)"
            ),
            Column(
                "sku",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Stock Keeping Unit"
            ),
            Column(
                "product_name",
                "VARCHAR",
                length=500,
                nullable=False,
                comment="Product name"
            ),
            Column(
                "brand",
                "VARCHAR",
                length=100,
                comment="Product brand"
            ),
            Column(
                "category_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_product_categories"
            ),
            Column(
                "description",
                "VARCHAR",
                length=2000,
                comment="Detailed product description"
            ),
            Column(
                "unit_price",
                "NUMBER",
                precision=10,
                scale=2,
                nullable=False,
                comment="Retail price"
            ),
            Column(
                "unit_cost",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Product cost"
            ),
            Column(
                "weight_kg",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Product weight in kg"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Product currently active"
            ),
            Column(
                "is_discontinued",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Product discontinued"
            ),
            # SCD Type 2 columns
            Column(
                "effective_date",
                "DATE",
                nullable=False,
                comment="SCD effective start date"
            ),
            Column(
                "end_date",
                "DATE",
                comment="SCD effective end date (NULL = current)"
            ),
            Column(
                "is_current",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Current version flag"
            ),
            Column(
                "created_at",
                "TIMESTAMP_NTZ",
                nullable=False,
                comment="Record creation timestamp"
            ),
            Column(
                "updated_at",
                "TIMESTAMP_NTZ",
                comment="Last update timestamp"
            ),
        ]
    
    foreign_keys = [
        ForeignKey(
            column="category_key",
            reference_table="dim_product_categories",
            reference_column="category_key"
        )
    ]
