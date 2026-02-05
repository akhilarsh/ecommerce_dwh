"""
Product Promotions Bridge Table Model.

Handles many-to-many relationship between products and promotions.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class BridgeProductPromotions(BaseTable):
    """Bridge table linking products to promotions."""
    
    table_name = "bridge_product_promotions"
    primary_key = ["product_promotion_key"]
    cluster_keys = ["product_key", "promotion_key"]
    comment = "Links products to applicable promotions"
    
    def define_columns(self) -> List[Column]:
        """Define product promotions bridge table columns."""
        return [
            Column(
                "product_promotion_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            # Foreign keys
            Column(
                "product_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_products"
            ),
            Column(
                "promotion_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_promotions"
            ),
            # Promotion details for this product
            Column(
                "is_featured",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Product is featured in promotion"
            ),
            Column(
                "priority",
                "NUMBER",
                precision=3,
                comment="Promotion priority if multiple apply"
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
            column="product_key",
            reference_table="dim_products",
            reference_column="product_key"
        ),
        ForeignKey(
            column="promotion_key",
            reference_table="dim_promotions",
            reference_column="promotion_key"
        ),
    ]
