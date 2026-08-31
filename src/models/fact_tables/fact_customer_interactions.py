"""
Customer Interaction Fact Table Model.

Tracks customer touchpoints (website visits, store visits, support calls, etc.).
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class FactCustomerInteractions(BaseTable):
    """Customer interaction fact table - tracks touchpoints."""
    
    table_name = "fact_customer_interactions"
    primary_key = ["interaction_key"]
    cluster_keys = ["date_key", "customer_key"]
    comment = "Customer touchpoints and interactions"
    
    def define_columns(self) -> List[Column]:
        """Define customer interaction fact table columns."""
        return [
            Column(
                "interaction_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "interaction_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business interaction identifier"
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
                "channel_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_channels"
            ),
            Column(
                "store_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_stores (for in-store interactions)"
            ),
            Column(
                "employee_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_employees (if assisted)"
            ),
            Column(
                "product_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_products (if product-related)"
            ),
            Column(
                "sale_key",
                "NUMBER",
                precision=38,
                comment="FK to fact_sales if purchase made"
            ),
            # Interaction details
            Column(
                "interaction_type",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Page View, Product View, Add to Cart, Remove from Cart, Wishlist Add, Search, Store Visit, Customer Service Call, Email Open, Email Click, App Session"
            ),
            Column(
                "device_type",
                "VARCHAR",
                length=50,
                comment="Desktop, Mobile, Tablet, In-Store Kiosk, Phone"
            ),
            Column(
                "session_id",
                "VARCHAR",
                length=100,
                comment="Session identifier for web visits"
            ),
            Column(
                "page_url",
                "VARCHAR",
                length=1000,
                comment="Page URL for web visits"
            ),
            Column(
                "duration_seconds",
                "NUMBER",
                precision=10,
                comment="Duration of interaction in seconds"
            ),
            Column(
                "is_converted",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Did interaction result in purchase"
            ),
            Column(
                "created_at",
                "TIMESTAMP_NTZ",
                nullable=False,
                comment="Record creation timestamp"
            ),
            Column(
                "event_properties",
                "VARIANT",
                comment="Raw event properties as semi-structured JSON (VARIANT)"
            ),
            Column(
                "geo_location",
                "GEOGRAPHY",
                comment="Interaction geospatial location (GEOGRAPHY)"
            ),
            Column(
                "raw_payload",
                "BINARY",
                comment="Raw binary event payload (BINARY)"
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
            column="channel_key",
            reference_table="dim_channels",
            reference_column="channel_key"
        ),
        ForeignKey(
            column="store_key",
            reference_table="dim_stores",
            reference_column="store_key"
        ),
        ForeignKey(
            column="employee_key",
            reference_table="dim_employees",
            reference_column="employee_key"
        ),
        ForeignKey(
            column="product_key",
            reference_table="dim_products",
            reference_column="product_key"
        ),
        ForeignKey(
            column="sale_key",
            reference_table="fact_sales",
            reference_column="sale_key"
        ),
    ]
