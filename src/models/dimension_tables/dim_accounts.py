"""
Account Dimension Table Model.

Defines customer accounts (individual, household, business, corporate).
"""

from typing import List
from ..base_table import BaseTable, Column


class DimAccounts(BaseTable):
    """Account dimension for organizational/billing entities."""

    table_name = "dim_accounts"
    primary_key = ["account_key"]
    comment = "Customer accounts - individual, household, business, corporate"

    def define_columns(self) -> List[Column]:
        """Define account dimension columns."""
        return [
            Column(
                "account_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "account_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business account identifier"
            ),
            Column(
                "account_name",
                "VARCHAR",
                length=200,
                nullable=False,
                comment="Display name for the account"
            ),
            Column(
                "account_type",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Individual, Household, Business, Corporate, Guest"
            ),
            Column(
                "company_name",
                "VARCHAR",
                length=200,
                comment="Company name for B2B accounts"
            ),
            Column(
                "tax_id",
                "VARCHAR",
                length=50,
                comment="Tax identification number"
            ),
            Column(
                "tax_exempt_status",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Tax exempt flag for B2B"
            ),
            Column(
                "billing_address_line1",
                "VARCHAR",
                length=500,
                comment="Billing street address line 1"
            ),
            Column(
                "billing_address_line2",
                "VARCHAR",
                length=500,
                comment="Billing street address line 2"
            ),
            Column(
                "billing_city",
                "VARCHAR",
                length=100,
                comment="Billing city"
            ),
            Column(
                "billing_state",
                "VARCHAR",
                length=50,
                comment="Billing state/province"
            ),
            Column(
                "billing_postal_code",
                "VARCHAR",
                length=20,
                comment="Billing ZIP/postal code"
            ),
            Column(
                "billing_country",
                "VARCHAR",
                length=100,
                comment="Billing country"
            ),
            Column(
                "payment_terms",
                "VARCHAR",
                length=50,
                comment="NET-30, NET-60, Due on Receipt"
            ),
            Column(
                "credit_limit",
                "NUMBER",
                precision=15,
                scale=2,
                comment="Credit limit for B2B accounts"
            ),
            Column(
                "account_status",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Active, Suspended, Closed, Pending"
            ),
            Column(
                "account_tier",
                "VARCHAR",
                length=50,
                comment="Standard, Premium, Enterprise"
            ),
            Column(
                "registration_date",
                "DATE",
                nullable=False,
                comment="Account creation date"
            ),
            Column(
                "closure_date",
                "DATE",
                comment="Account closure date (NULL = open)"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Account currently active"
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
