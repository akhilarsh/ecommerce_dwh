"""
Sales Fact Table Model.

Core sales transactions - the central fact table in the star schema.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class FactSales(BaseTable):
    """Sales fact table - central hub of the star schema."""
    
    table_name = "fact_sales"
    primary_key = ["sale_key"]
    cluster_keys = ["date_key", "customer_key"]
    comment = "Core sales transactions fact table"
    
    def define_columns(self) -> List[Column]:
        """Define sales fact table columns."""
        return [
            Column(
                "sale_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key for each sale transaction"
            ),
            Column(
                "order_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business order identifier"
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
                "store_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_stores (NULL for online orders)"
            ),
            Column(
                "channel_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_channels"
            ),
            Column(
                "promotion_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_promotions (NULL if no promotion)"
            ),
            Column(
                "payment_method_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_payment_methods"
            ),
            Column(
                "shipping_method_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_shipping_methods"
            ),
            Column(
                "employee_key",
                "NUMBER",
                precision=38,
                comment="FK to dim_employees (NULL for online orders)"
            ),
            # Measures
            Column(
                "quantity",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Total items in order"
            ),
            Column(
                "gross_amount",
                "NUMBER",
                precision=15,
                scale=2,
                nullable=False,
                comment="Order total before discounts"
            ),
            Column(
                "discount_amount",
                "NUMBER",
                precision=15,
                scale=2,
                default="0",
                comment="Total discount applied"
            ),
            Column(
                "net_amount",
                "NUMBER",
                precision=15,
                scale=2,
                nullable=False,
                comment="Amount after discount (gross - discount)"
            ),
            Column(
                "tax_amount",
                "NUMBER",
                precision=15,
                scale=2,
                default="0",
                comment="Sales tax"
            ),
            Column(
                "shipping_amount",
                "NUMBER",
                precision=15,
                scale=2,
                default="0",
                comment="Shipping charges"
            ),
            Column(
                "total_amount",
                "NUMBER",
                precision=15,
                scale=2,
                nullable=False,
                comment="Final order total (net + tax + shipping)"
            ),
            # Additional attributes
            Column(
                "order_status",
                "VARCHAR",
                length=50,
                comment="Completed, Cancelled, Returned, Pending"
            ),
            Column(
                "is_online",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Online order flag"
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
            column="store_key",
            reference_table="dim_stores",
            reference_column="store_key"
        ),
        ForeignKey(
            column="channel_key",
            reference_table="dim_channels",
            reference_column="channel_key"
        ),
        ForeignKey(
            column="promotion_key",
            reference_table="dim_promotions",
            reference_column="promotion_key"
        ),
        ForeignKey(
            column="payment_method_key",
            reference_table="dim_payment_methods",
            reference_column="payment_method_key"
        ),
        ForeignKey(
            column="shipping_method_key",
            reference_table="dim_shipping_methods",
            reference_column="shipping_method_key"
        ),
        ForeignKey(
            column="employee_key",
            reference_table="dim_employees",
            reference_column="employee_key"
        ),
    ]
