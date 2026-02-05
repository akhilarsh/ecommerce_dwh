"""
Customer Dimension Table Model.

Customer master data with SCD Type 2 for tracking history of customer changes.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class DimCustomers(BaseTable):
    """Customer dimension with SCD Type 2."""
    
    table_name = "dim_customers"
    primary_key = ["customer_key"]
    comment = "Customer master data with historical tracking (SCD Type 2)"
    
    def define_columns(self) -> List[Column]:
        """Define customer dimension columns."""
        return [
            Column(
                "customer_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "customer_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business customer identifier (natural key)"
            ),
            Column(
                "first_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Customer first name"
            ),
            Column(
                "last_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Customer last name"
            ),
            Column(
                "full_name",
                "VARCHAR",
                length=200,
                comment="Full name (first + last)"
            ),
            Column(
                "email",
                "VARCHAR",
                length=200,
                comment="Customer email address"
            ),
            Column(
                "phone_number",
                "VARCHAR",
                length=20,
                comment="Customer phone number"
            ),
            Column(
                "birth_date",
                "DATE",
                comment="Customer date of birth"
            ),
            Column(
                "gender",
                "VARCHAR",
                length=20,
                comment="M, F, Other, Prefer not to say"
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
            Column(
                "segment_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_customer_segments"
            ),
            Column(
                "preferred_channel",
                "VARCHAR",
                length=50,
                comment="Preferred shopping channel"
            ),
            Column(
                "loyalty_program_member",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Member of loyalty program"
            ),
            Column(
                "loyalty_tier",
                "VARCHAR",
                length=50,
                comment="Bronze, Silver, Gold, Platinum"
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
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Customer account active"
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
            column="segment_key",
            reference_table="dim_customer_segments",
            reference_column="segment_key"
        )
    ]
