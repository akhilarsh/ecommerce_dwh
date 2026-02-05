"""
Sales Channel Dimension Table Model.

Defines the various sales channels (online, in-store, mobile app, etc.).
"""

from typing import List
from ..base_table import BaseTable, Column


class DimChannels(BaseTable):
    """Sales channel dimension."""
    
    table_name = "dim_channels"
    primary_key = ["channel_key"]
    comment = "Sales channels (online, in-store, mobile, etc.)"
    
    def define_columns(self) -> List[Column]:
        """Define channel dimension columns."""
        return [
            Column(
                "channel_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "channel_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business channel identifier"
            ),
            Column(
                "channel_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Web, In-Store, Mobile App, Call Center"
            ),
            Column(
                "channel_code",
                "VARCHAR",
                length=20,
                nullable=False,
                comment="Short code for channel"
            ),
            Column(
                "channel_type",
                "VARCHAR",
                length=50,
                comment="Digital, Physical, Hybrid"
            ),
            Column(
                "description",
                "VARCHAR",
                length=500,
                comment="Detailed description"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Channel currently active"
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
