"""
Promotion Dimension Table Model.

Defines marketing campaigns and promotional offers.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimPromotions(BaseTable):
    """Promotion dimension."""
    
    table_name = "dim_promotions"
    primary_key = ["promotion_key"]
    comment = "Marketing promotions and campaigns"
    
    def define_columns(self) -> List[Column]:
        """Define promotion dimension columns."""
        return [
            Column(
                "promotion_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "promotion_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business promotion identifier"
            ),
            Column(
                "promotion_name",
                "VARCHAR",
                length=200,
                nullable=False,
                comment="Promotion campaign name"
            ),
            Column(
                "promotion_type",
                "VARCHAR",
                length=50,
                comment="Percentage, Fixed Amount, BOGO, Free Shipping"
            ),
            Column(
                "promotion_code",
                "VARCHAR",
                length=50,
                comment="Promo code for redemption"
            ),
            Column(
                "start_date",
                "DATE",
                nullable=False,
                comment="Promotion start date"
            ),
            Column(
                "end_date",
                "DATE",
                nullable=False,
                comment="Promotion end date"
            ),
            Column(
                "discount_percentage",
                "NUMBER",
                precision=5,
                scale=2,
                comment="Discount percentage (0-100)"
            ),
            Column(
                "discount_amount",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Fixed discount amount"
            ),
            Column(
                "min_purchase_amount",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Minimum purchase required"
            ),
            Column(
                "max_discount_amount",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Maximum discount cap"
            ),
            Column(
                "is_stackable",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Can combine with other promotions"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Promotion currently active"
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
