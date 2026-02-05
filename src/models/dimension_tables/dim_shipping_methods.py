"""
Shipping Method Dimension Table Model.

Defines fulfillment and shipping options.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimShippingMethods(BaseTable):
    """Shipping method dimension."""
    
    table_name = "dim_shipping_methods"
    primary_key = ["shipping_method_key"]
    comment = "Shipping and fulfillment methods"
    
    def define_columns(self) -> List[Column]:
        """Define shipping method dimension columns."""
        return [
            Column(
                "shipping_method_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "shipping_method_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business shipping method identifier"
            ),
            Column(
                "shipping_method_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Standard, Express, Same Day, In-Store Pickup"
            ),
            Column(
                "shipping_method_code",
                "VARCHAR",
                length=20,
                nullable=False,
                comment="Short code for shipping method"
            ),
            Column(
                "carrier",
                "VARCHAR",
                length=100,
                comment="Shipping carrier (FedEx, UPS, USPS, etc.)"
            ),
            Column(
                "estimated_days_min",
                "NUMBER",
                precision=3,
                comment="Minimum delivery days"
            ),
            Column(
                "estimated_days_max",
                "NUMBER",
                precision=3,
                comment="Maximum delivery days"
            ),
            Column(
                "base_cost",
                "NUMBER",
                precision=10,
                scale=2,
                comment="Base shipping cost"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Shipping method currently active"
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
