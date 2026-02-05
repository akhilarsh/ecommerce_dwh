"""
Customer Segment Dimension Table Model.

Defines customer segmentation groups for targeted marketing and analysis.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimCustomerSegments(BaseTable):
    """Customer segment dimension."""
    
    table_name = "dim_customer_segments"
    primary_key = ["segment_key"]
    comment = "Customer segmentation groups (VIP, Regular, New, etc.)"
    
    def define_columns(self) -> List[Column]:
        """Define customer segment dimension columns."""
        return [
            Column(
                "segment_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "segment_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business segment identifier"
            ),
            Column(
                "segment_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="VIP, High Value, Regular, New Customer, At Risk"
            ),
            Column(
                "segment_code",
                "VARCHAR",
                length=20,
                nullable=False,
                comment="Short code for segment"
            ),
            Column(
                "description",
                "VARCHAR",
                length=500,
                comment="Detailed segment description"
            ),
            Column(
                "min_lifetime_value",
                "NUMBER",
                precision=12,
                scale=2,
                comment="Minimum LTV for this segment"
            ),
            Column(
                "max_lifetime_value",
                "NUMBER",
                precision=12,
                scale=2,
                comment="Maximum LTV for this segment"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Segment currently active"
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
