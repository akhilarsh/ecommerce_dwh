"""
Order Items Bridge Table Model.

Handles many-to-many relationship between orders and products (order line items).
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class BridgeOrderItems(BaseTable):
    """Bridge table linking sales orders to products (line items)."""
    
    table_name = "bridge_order_items"
    primary_key = ["order_item_key"]
    cluster_keys = ["sale_key", "product_key"]
    comment = "Order line items - links orders to products"
    
    def define_columns(self) -> List[Column]:
        """Define order items bridge table columns."""
        return [
            Column(
                "order_item_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key for each line item"
            ),
            # Foreign keys
            Column(
                "sale_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to fact_sales"
            ),
            Column(
                "product_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="FK to dim_products"
            ),
            # Line item details
            Column(
                "line_number",
                "NUMBER",
                precision=5,
                nullable=False,
                comment="Line number within order"
            ),
            Column(
                "quantity",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Quantity of this product in order"
            ),
            Column(
                "unit_price",
                "NUMBER",
                precision=10,
                scale=2,
                nullable=False,
                comment="Unit price at time of sale"
            ),
            Column(
                "discount_amount",
                "NUMBER",
                precision=10,
                scale=2,
                default="0",
                comment="Discount applied to this line item"
            ),
            Column(
                "line_total",
                "NUMBER",
                precision=15,
                scale=2,
                nullable=False,
                comment="Line total (quantity * unit_price - discount)"
            ),
            Column(
                "is_gift",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="Item is a gift"
            ),
            Column(
                "gift_message",
                "VARCHAR",
                length=500,
                comment="Gift message"
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
            column="sale_key",
            reference_table="fact_sales",
            reference_column="sale_key"
        ),
        ForeignKey(
            column="product_key",
            reference_table="dim_products",
            reference_column="product_key"
        ),
    ]
