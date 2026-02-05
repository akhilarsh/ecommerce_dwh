"""
Loyalty Points Fact Table Model.

Tracks loyalty program point transactions (earned, redeemed, expired).
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class FactLoyaltyPoints(BaseTable):
    """Loyalty points transaction fact table."""
    
    table_name = "fact_loyalty_points"
    primary_key = ["loyalty_transaction_key"]
    cluster_keys = ["date_key", "customer_key"]
    comment = "Loyalty program point transactions"
    
    def define_columns(self) -> List[Column]:
        """Define loyalty points fact table columns."""
        return [
            Column(
                "loyalty_transaction_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "transaction_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business transaction identifier"
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
                "time_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_time"
            ),
            Column(
                "customer_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_customers"
            ),
            Column(
                "sale_key",
                "NUMBER",
                precision=38,
                comment="FK to fact_sales (if points from purchase)"
            ),
            Column(
                "channel_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_channels"
            ),
            # Transaction details
            Column(
                "transaction_type",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Earned, Redeemed, Expired, Adjusted, Bonus"
            ),
            Column(
                "points",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Point amount (positive for earned, negative for redeemed)"
            ),
            Column(
                "points_balance_after",
                "NUMBER",
                precision=10,
                comment="Customer point balance after transaction"
            ),
            Column(
                "description",
                "VARCHAR",
                length=500,
                comment="Description of transaction"
            ),
            Column(
                "expiration_date",
                "DATE",
                comment="When these points will expire"
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
            column="time_key",
            reference_table="dim_time",
            reference_column="time_key"
        ),
        ForeignKey(
            column="customer_key",
            reference_table="dim_customers",
            reference_column="customer_key"
        ),
        ForeignKey(
            column="sale_key",
            reference_table="fact_sales",
            reference_column="sale_key"
        ),
        ForeignKey(
            column="channel_key",
            reference_table="dim_channels",
            reference_column="channel_key"
        ),
    ]
