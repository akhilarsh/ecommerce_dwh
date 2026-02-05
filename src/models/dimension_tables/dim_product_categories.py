"""
Product Category Dimension Table Model.

Defines product hierarchy (Category > Subcategory > Brand).
"""

from typing import List
from ..base_table import BaseTable, Column


class DimProductCategories(BaseTable):
    """Product category dimension with hierarchy."""
    
    table_name = "dim_product_categories"
    primary_key = ["category_key"]
    comment = "Product category hierarchy"
    
    def define_columns(self) -> List[Column]:
        """Define product category dimension columns."""
        return [
            Column(
                "category_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "category_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business category identifier"
            ),
            Column(
                "category_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Category name"
            ),
            Column(
                "category_level",
                "NUMBER",
                precision=1,
                comment="Hierarchy level (1=Category, 2=Subcategory, 3=Brand)"
            ),
            Column(
                "parent_category_key",
                "NUMBER",
                precision=38,
                comment="Parent category for hierarchy navigation"
            ),
            Column(
                "category_path",
                "VARCHAR",
                length=500,
                comment="Full hierarchy path (e.g., Electronics > Phones > Apple)"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Category currently active"
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
