"""
Dimension generator for dim_customers.

Generates customer records with SCD Type 2 support.
"""

import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class DimCustomersGenerator(BaseEntityGenerator):
    """Generator for dim_customers table (SCD Type 2)."""
    
    table_name = "dim_customers"
    
    PREFERRED_CHANNELS = ["Online Web", "Mobile App", "In-Store", "Phone Order"]
    
    # Country -> phone code mapping (weighted by customer distribution)
    COUNTRIES = [
        ("USA", "+1", 0.40),
        ("Canada", "+1", 0.08),
        ("UK", "+44", 0.08),
        ("Germany", "+49", 0.07),
        ("France", "+33", 0.05),
        ("Australia", "+61", 0.05),
        ("Japan", "+81", 0.05),
        ("India", "+91", 0.10),
        ("Brazil", "+55", 0.04),
        ("Mexico", "+52", 0.03),
        ("Singapore", "+65", 0.03),
        ("Argentina", "+54", 0.02),
    ]
    
    # Tier weights for point generation: (weight, min_pts, max_pts)
    # Reflects realistic loyalty distribution skewed toward lower tiers
    _DEFAULT_TIER_DISTRIBUTION = [
        (0.40, 0, 999),       # Bronze
        (0.30, 1000, 3999),   # Silver
        (0.20, 4000, 9999),   # Gold
        (0.10, 10000, 50000), # Platinum
    ]

    def generate(
        self,
        count: int = 1000,
        start_key: int = 1,
        segment_keys: List[int] = None,
        account_keys: List[int] = None,
        loyalty_tier_data: Optional[List[Dict[str, Any]]] = None,
        registration_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        effective_date: Optional[date] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate customer dimension records.
        
        Args:
            count: Number of customers to generate
            start_key: Starting surrogate key value
            segment_keys: List of valid segment keys
            account_keys: List of valid account keys (primary account assignment)
            loyalty_tier_data: List of dicts with tier_key, min_points, max_points.
                               If None, uses default tier thresholds with key positions 1–4.
            registration_date: Specific registration date (single date, for backwards compat)
            start_date: Start of date range for registration dates
            end_date: End of date range for registration dates
            effective_date: SCD effective date
            
        Returns:
            GeneratedData with customer dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )

        self.logger.info(f"Generating {count} customers")

        # Default segment keys if not provided
        if not segment_keys:
            segment_keys = list(range(1, 8))  # 7 standard segments

        # Build tier lookup: list of (tier_key, min_points, max_points) sorted by min_points
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
            # Fallback: derive keys from position (tier_key = 1..4 for Bronze..Platinum)
            tier_lookup = [(i + 1, mn, mx) for i, (_, mn, mx) in enumerate(self._DEFAULT_TIER_DISTRIBUTION)]
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
            return tier_lookup[-1][0]  # fallback to highest tier
        
        # Date setup
        eff_date = effective_date or self.config.dates.start
        end_date = date(9999, 12, 31)
        
        records = []
        keys = []
        now = datetime.now()
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Generate customer attributes
            first_name = self.faker.first_name()
            last_name = self.faker.last_name()
            
            # Registration date - specific, range, or config default
            if registration_date:
                reg_date = registration_date
            elif start_date and end_date:
                reg_date = self.faker.date_between(
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                reg_date = self.faker.date_between(
                    start_date=self.config.dates.start or date(2024, 1, 1),
                    end_date=self.config.dates.end or date(2024, 12, 31)
                )
            
            # Birth date - customers are 18-80 years old
            birth_date = self.faker.date_of_birth(
                minimum_age=18,
                maximum_age=80
            )
            
            # Email generation
            email_domain = random.choice([
                "gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"
            ])
            email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@{email_domain}"
            
            # Loyalty program - 60% are members
            is_loyalty_member = random.random() < 0.6
            loyalty_tier_key = None
            loyalty_points = 0

            if is_loyalty_member:
                # Pick a tier band by weight, then generate points within that band
                chosen_range = random.choices(tier_ranges, weights=tier_weights)[0]
                loyalty_points = random.randint(chosen_range[0], chosen_range[1])
                loyalty_tier_key = _points_to_tier_key(loyalty_points)
            
            # Assign segment - weighted toward New/Regular for fresh data
            segment_weights = [0.05, 0.15, 0.30, 0.30, 0.10, 0.07, 0.03]
            segment_key = random.choices(segment_keys, weights=segment_weights[:len(segment_keys)])[0]
            
            # Pick country with weighted distribution
            countries, codes, weights = zip(*self.COUNTRIES)
            country_idx = random.choices(range(len(countries)), weights=weights)[0]
            country = countries[country_idx]
            country_code = codes[country_idx]
            
            # State only for certain countries
            state = self.faker.state_abbr() if country in ["USA", "Canada", "Australia"] else None
            
            if account_keys:
                if i < len(account_keys):
                    account_key = account_keys[i]
                else:
                    self.logger.warning(
                        f"Customer {key}: no account_key available (index {i} >= {len(account_keys)} accounts). "
                        "1:1 mapping requires equal account and customer counts."
                    )
                    account_key = None
            else:
                account_key = None

            record = {
                "customer_key": key,
                "customer_id": f"CUST{key:08d}",
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "email": email,
                "phone_number": self.faker.numerify(f"{country_code}-###-###-####"),
                "birth_date": birth_date,
                "gender": random.choice(["M", "F", "O", None]),
                "address_line1": self.faker.street_address(),
                "address_line2": self.faker.secondary_address() if random.random() < 0.2 else None,
                "city": self.faker.city(),
                "state": state,
                "postal_code": self.faker.zipcode(),
                "country": country,
                "registration_date": reg_date,
                "segment_key": segment_key,
                "account_key": account_key,
                "preferred_channel": random.choice(self.PREFERRED_CHANNELS),
                "loyalty_program_member": is_loyalty_member,
                "loyalty_tier_key": loyalty_tier_key,
                "loyalty_points_balance": loyalty_points,
                "lifetime_value": Decimal("0.00"),  # Updated by ETL
                "is_active": True,
                # SCD Type 2 columns
                "effective_date": eff_date,
                "end_date": end_date,
                "is_current": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} customer records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
