"""
Store Dimension Table Model.

Defines physical store locations.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimStores(BaseTable):
    """Store location dimension."""
    
    table_name = "dim_stores"
    primary_key = ["store_key"]
    comment = "Physical store locations"
    
    def define_columns(self) -> List[Column]:
        """Define store dimension columns."""
        return [
            Column(
                "store_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "store_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business store identifier"
            ),
            Column(
                "store_name",
                "VARCHAR",
                length=200,
                nullable=False,
                comment="Store name"
            ),
            Column(
                "store_type",
                "VARCHAR",
                length=50,
                comment="Flagship, Mall, Outlet, Warehouse"
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
                nullable=False,
                comment="Country"
            ),
            Column(
                "region",
                "VARCHAR",
                length=100,
                comment="Geographic region"
            ),
            Column(
                "phone_number",
                "VARCHAR",
                length=20,
                comment="Store phone number"
            ),
            Column(
                "email",
                "VARCHAR",
                length=200,
                comment="Store email address"
            ),
            Column(
                "opening_date",
                "DATE",
                comment="Store opening date"
            ),
            Column(
                "closing_date",
                "DATE",
                comment="Store closing date (if closed)"
            ),
            Column(
                "square_footage",
                "NUMBER",
                precision=10,
                comment="Store size in square feet"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Store currently active"
            ),
            Column(
                "latitude",
                "NUMBER",
                precision=10,
                scale=6,
                comment="Geographic latitude"
            ),
            Column(
                "longitude",
                "NUMBER",
                precision=10,
                scale=6,
                comment="Geographic longitude"
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
