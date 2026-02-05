"""
Payment Method Dimension Table Model.

Defines payment methods (credit card, debit card, cash, etc.).
"""

from typing import List
from ..base_table import BaseTable, Column


class DimPaymentMethods(BaseTable):
    """Payment method dimension."""
    
    table_name = "dim_payment_methods"
    primary_key = ["payment_method_key"]
    comment = "Payment methods (credit, debit, cash, digital wallet, etc.)"
    
    def define_columns(self) -> List[Column]:
        """Define payment method dimension columns."""
        return [
            Column(
                "payment_method_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "payment_method_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business payment method identifier"
            ),
            Column(
                "payment_method_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Credit Card, Debit Card, Cash, PayPal, etc."
            ),
            Column(
                "payment_method_code",
                "VARCHAR",
                length=20,
                nullable=False,
                comment="Short code for payment method"
            ),
            Column(
                "payment_type",
                "VARCHAR",
                length=50,
                comment="Card, Cash, Digital Wallet, Bank Transfer"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Payment method currently active"
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
