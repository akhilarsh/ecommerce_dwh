"""
Customer Address Dimension Table Model.

Customer shipping/registration address with SCD Type 2 for tracking address changes.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class DimCustomerAddress(BaseTable):
    """Customer address dimension with SCD Type 2."""

    table_name = "dim_customer_address"
    primary_key = ["address_key"]
    comment = "Customer addresses with historical tracking (SCD Type 2)"

    def define_columns(self) -> List[Column]:
        """Define customer address dimension columns."""
        return [
            Column(
                "address_key",
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
                "address_line1",
                "VARCHAR",
                length=500,
                comment="Street address line 1"
            ),
            Column(
                "address_line2",
                "VARCHAR",
                length=500,
                comment="Street address line 2"
            ),
            Column(
                "city",
                "VARCHAR",
                length=100,
                comment="City"
            ),
            Column(
                "state",
                "VARCHAR",
                length=50,
                comment="State/Province"
            ),
            Column(
                "postal_code",
                "VARCHAR",
                length=20,
                comment="ZIP/Postal code"
            ),
            Column(
                "country",
                "VARCHAR",
                length=100,
                comment="Country"
            ),
            Column(
                "registration_date",
                "DATE",
                nullable=False,
                comment="Customer registration date"
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
    ]
