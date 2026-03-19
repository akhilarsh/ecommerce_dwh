"""
Loyalty Tier Dimension Table Model.

Defines loyalty program tier definitions with point thresholds.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimLoyaltyTiers(BaseTable):
    """Loyalty tier dimension with point range thresholds."""

    table_name = "dim_loyalty_tiers"
    primary_key = ["tier_key"]
    comment = "Loyalty program tier definitions with point thresholds"

    def define_columns(self) -> List[Column]:
        """Define loyalty tier dimension columns."""
        return [
            Column(
                "tier_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "tier_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business tier identifier (BRONZE, SILVER, GOLD, PLATINUM)"
            ),
            Column(
                "tier_name",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Display name (Bronze, Silver, Gold, Platinum)"
            ),
            Column(
                "min_points",
                "NUMBER",
                precision=10,
                nullable=False,
                comment="Minimum points required for this tier (inclusive)"
            ),
            Column(
                "max_points",
                "NUMBER",
                precision=10,
                comment="Maximum points for this tier (inclusive, NULL = no upper limit)"
            ),
            Column(
                "description",
                "VARCHAR",
                length=500,
                comment="Tier description and benefits summary"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Tier currently active"
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
