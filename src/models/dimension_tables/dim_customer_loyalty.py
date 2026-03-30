"""
Customer Loyalty Dimension Table Model.

Customer loyalty program metrics with SCD Type 2 for tracking loyalty status changes.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class DimCustomerLoyalty(BaseTable):
    """Customer loyalty dimension with SCD Type 2."""

    table_name = "dim_customer_loyalty"
    primary_key = ["loyalty_key"]
    comment = "Customer loyalty program metrics with historical tracking (SCD Type 2)"

    def define_columns(self) -> List[Column]:
        """Define customer loyalty dimension columns."""
        return [
            Column(
                "loyalty_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "customer_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_customers"
            ),
            Column(
                "loyalty_program_member",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Member of loyalty program"
            ),
            Column(
                "loyalty_tier_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_loyalty_tiers (NULL for non-members)"
            ),
            Column(
                "loyalty_points_balance",
                "NUMBER",
                precision=10,
                comment="Current loyalty points balance"
            ),
            Column(
                "lifetime_value",
                "NUMBER",
                precision=12,
                scale=2,
                comment="Total lifetime purchase value"
            ),
            Column(
                "account_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_accounts (primary account)"
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
            column="customer_key",
            reference_table="dim_customers",
            reference_column="customer_key"
        ),
        ForeignKey(
            column="loyalty_tier_key",
            reference_table="dim_loyalty_tiers",
            reference_column="tier_key"
        ),
        ForeignKey(
            column="account_key",
            reference_table="dim_accounts",
            reference_column="account_key"
        ),
    ]
