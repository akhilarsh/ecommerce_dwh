"""
Dimension generator for dim_loyalty_tier.

Generates loyalty tier records with point threshold definitions.
"""

from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimLoyaltyTiersGenerator(BaseEntityGenerator):
    """Generator for dim_loyalty_tiers table."""

    table_name = "dim_loyalty_tiers"

    TIERS = [
        {
            "tier_id": "BRONZE",
            "tier_name": "Bronze",
            "min_points": 0,
            "max_points": 999,
            "description": "Entry-level tier for new loyalty members (0–999 points)",
            "is_active": True,
        },
        {
            "tier_id": "SILVER",
            "tier_name": "Silver",
            "min_points": 1000,
            "max_points": 3999,
            "description": "Mid-tier members with consistent engagement (1,000–3,999 points)",
            "is_active": True,
        },
        {
            "tier_id": "GOLD",
            "tier_name": "Gold",
            "min_points": 4000,
            "max_points": 9999,
            "description": "High-value members with premium benefits (4,000–9,999 points)",
            "is_active": True,
        },
        {
            "tier_id": "PLATINUM",
            "tier_name": "Platinum",
            "min_points": 10000,
            "max_points": None,
            "description": "Elite tier for top loyalty members (10,000+ points)",
            "is_active": True,
        },
    ]

    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate loyalty tier dimension records.

        Args:
            count: Ignored — all standard tiers are generated
            start_key: Starting surrogate key value

        Returns:
            GeneratedData with loyalty tier dimension records
        """
        self.logger.info("Generating loyalty tier dimension")

        records = []
        keys = []
        now = datetime.now()

        for i, tier in enumerate(self.TIERS):
            key = start_key + i
            keys.append(key)

            record = {
                "tier_key": key,
                **tier,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)

        df = self._create_dataframe(records)

        self.logger.info(f"Generated {len(records)} loyalty tier records")

        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
