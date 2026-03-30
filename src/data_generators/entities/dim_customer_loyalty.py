"""
Dimension generator for dim_customer_loyalty.

Generates one loyalty record per customer with SCD Type 2 support.
"""

import random
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class DimCustomerLoyaltyGenerator(BaseEntityGenerator):
    """Generator for dim_customer_loyalty table (SCD Type 2)."""

    table_name = "dim_customer_loyalty"

    # Tier weights for point generation: (weight, min_pts, max_pts)
    _DEFAULT_TIER_DISTRIBUTION = [
        (0.40, 0, 999),        # Bronze
        (0.30, 1000, 3999),    # Silver
        (0.20, 4000, 9999),    # Gold
        (0.10, 10000, 50000),  # Platinum
    ]

    def generate(
        self,
        customer_keys: List[int],
        start_key: int = 1,
        account_keys: Optional[List[int]] = None,
        loyalty_tier_data: Optional[List[Dict[str, Any]]] = None,
        effective_date: Optional[date] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate one loyalty record per customer.

        Args:
            customer_keys: List of customer surrogate keys
            start_key: Starting surrogate key value for loyalty_key
            account_keys: List of valid account keys (primary account assignment)
            loyalty_tier_data: List of dicts with tier_key, min_points, max_points.
                               If None, uses default tier thresholds with key positions 1-4.
            effective_date: SCD effective date

        Returns:
            GeneratedData with customer loyalty records
        """
        if not customer_keys:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )

        self.logger.info(f"Generating {len(customer_keys)} customer loyalty records")

        # Build tier lookup
        if loyalty_tier_data:
            tier_lookup = sorted(
                [(t["tier_key"], t["min_points"], t.get("max_points")) for t in loyalty_tier_data],
                key=lambda x: x[1]
            )
            tier_distribution = [
                (w, mn, mx if mx is not None else 50000)
                for (_, mn, mx), (w, _, _) in zip(tier_lookup, self._DEFAULT_TIER_DISTRIBUTION)
            ]
        else:
            tier_lookup = [
                (i + 1, mn, mx)
                for i, (_, mn, mx) in enumerate(self._DEFAULT_TIER_DISTRIBUTION)
            ]
            tier_distribution = self._DEFAULT_TIER_DISTRIBUTION

        tier_weights = [w for w, _, _ in tier_distribution]
        tier_ranges = [(mn, mx) for _, mn, mx in tier_distribution]

        def _points_to_tier_key(points: int) -> int:
            for tier_key, min_pts, max_pts in tier_lookup:
                if max_pts is None:
                    if points >= min_pts:
                        return tier_key
                elif min_pts <= points <= max_pts:
                    return tier_key
            return tier_lookup[-1][0]

        eff_date = effective_date or self.config.dates.start
        scd_end_date = date(9999, 12, 31)

        records = []
        keys = []
        now = datetime.now()

        for i, customer_key in enumerate(customer_keys):
            key = start_key + i
            keys.append(key)

            is_loyalty_member = random.random() < 0.6
            loyalty_tier_key = None
            loyalty_points = 0

            if is_loyalty_member:
                chosen_range = random.choices(tier_ranges, weights=tier_weights)[0]
                loyalty_points = random.randint(chosen_range[0], chosen_range[1])
                loyalty_tier_key = _points_to_tier_key(loyalty_points)

            account_key = random.choice(account_keys) if account_keys else None

            record = {
                "loyalty_key": key,
                "customer_key": customer_key,
                "loyalty_program_member": is_loyalty_member,
                "loyalty_tier_key": loyalty_tier_key,
                "loyalty_points_balance": loyalty_points,
                "lifetime_value": Decimal("0.00"),
                "account_key": account_key,
                # SCD Type 2 columns
                "effective_date": eff_date,
                "end_date": scd_end_date,
                "is_current": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)

        df = self._create_dataframe(records)
        self.logger.info(f"Generated {len(records)} customer loyalty records")

        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
