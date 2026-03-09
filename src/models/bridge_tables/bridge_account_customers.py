"""
Account-Customer Bridge Table Model.

Handles many-to-many relationship between accounts and customers with role context.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class BridgeAccountCustomers(BaseTable):
    """Bridge table linking accounts to customers with roles."""

    table_name = "bridge_account_customers"
    primary_key = ["account_customer_key"]
    cluster_keys = ["account_key", "customer_key"]
    comment = "Account-customer relationships with roles"

    def define_columns(self) -> List[Column]:
        """Define account-customer bridge table columns."""
        return [
            Column(
                "account_customer_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "account_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_accounts"
            ),
            Column(
                "customer_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_customers"
            ),
            Column(
                "role",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Owner, Admin, Buyer, Viewer, Member"
            ),
            Column(
                "is_primary_contact",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Primary contact for the account"
            ),
            Column(
                "effective_date",
                "DATE",
                nullable=False,
                comment="Relationship start date"
            ),
            Column(
                "end_date",
                "DATE",
                comment="Relationship end date (NULL = current)"
            ),
            Column(
                "is_current",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Current relationship flag"
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
            column="account_key",
            reference_table="dim_accounts",
            reference_column="account_key"
        ),
        ForeignKey(
            column="customer_key",
            reference_table="dim_customers",
            reference_column="customer_key"
        ),
    ]
