"""
Dimension generator for dim_customer_address.

Generates one address record per customer with SCD Type 2 support.
"""

import random
from datetime import datetime, date
from typing import List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class DimCustomerAddressGenerator(BaseEntityGenerator):
    """Generator for dim_customer_address table (SCD Type 2)."""

    table_name = "dim_customer_address"

    # Country -> state availability
    COUNTRIES_WITH_STATES = {"USA", "Canada", "Australia"}

    COUNTRIES = [
        ("USA", 0.40),
        ("Canada", 0.08),
        ("UK", 0.08),
        ("Germany", 0.07),
        ("France", 0.05),
        ("Australia", 0.05),
        ("Japan", 0.05),
        ("India", 0.10),
        ("Brazil", 0.04),
        ("Mexico", 0.03),
        ("Singapore", 0.03),
        ("Argentina", 0.02),
    ]

    def generate(
        self,
        customer_keys: List[int],
        start_key: int = 1,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        effective_date: Optional[date] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate one address record per customer.

        Args:
            customer_keys: List of customer surrogate keys to generate addresses for
            start_key: Starting surrogate key value for address_key
            start_date: Start of registration date range
            end_date: End of registration date range
            effective_date: SCD effective date

        Returns:
            GeneratedData with customer address records
        """
        if not customer_keys:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )

        self.logger.info(f"Generating {len(customer_keys)} customer addresses")

        eff_date = effective_date or self.config.dates.start
        scd_end_date = date(9999, 12, 31)
        reg_start = start_date or self.config.dates.start or date(2024, 1, 1)
        reg_end = end_date or self.config.dates.end or date(2024, 12, 31)

        countries, weights = zip(*self.COUNTRIES)

        records = []
        keys = []
        now = datetime.now()

        for i, customer_key in enumerate(customer_keys):
            key = start_key + i
            keys.append(key)

            country = random.choices(countries, weights=weights)[0]
            state = self.faker.state_abbr() if country in self.COUNTRIES_WITH_STATES else None
            registration_date = self.faker.date_between(
                start_date=reg_start,
                end_date=reg_end
            )

            record = {
                "address_key": key,
                "customer_key": customer_key,
                "address_line1": self.faker.street_address(),
                "address_line2": self.faker.secondary_address() if random.random() < 0.2 else None,
                "city": self.faker.city(),
                "state": state,
                "postal_code": self.faker.zipcode(),
                "country": country,
                "registration_date": registration_date,
                # SCD Type 2 columns
                "effective_date": eff_date,
                "end_date": scd_end_date,
                "is_current": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)

        df = self._create_dataframe(records)
        self.logger.info(f"Generated {len(records)} customer address records")

        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
