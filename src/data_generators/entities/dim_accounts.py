"""
Dimension generator for dim_accounts.

Generates account records with mixed types (Individual, Household, Business, Corporate, Guest).
"""

import random
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class DimAccountsGenerator(BaseEntityGenerator):
    """Generator for dim_accounts table."""

    table_name = "dim_accounts"

    ACCOUNT_TYPES = [
        ("Individual", 0.60),
        ("Household", 0.15),
        ("Business", 0.15),
        ("Corporate", 0.08),
        ("Guest", 0.02),
    ]

    ACCOUNT_TIERS = {
        "Individual": ["Standard", "Premium"],
        "Household": ["Standard", "Premium"],
        "Business": ["Standard", "Premium", "Enterprise"],
        "Corporate": ["Premium", "Enterprise"],
        "Guest": [None],
    }

    PAYMENT_TERMS = {
        "Individual": [None],
        "Household": [None],
        "Business": ["Due on Receipt", "NET-30"],
        "Corporate": ["NET-30", "NET-60"],
        "Guest": [None],
    }

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

    COMPANY_SUFFIXES = ["Inc.", "LLC", "Corp.", "Ltd.", "Group", "Holdings", "Co."]

    def generate(
        self,
        count: int = 200,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate account dimension records.

        Args:
            count: Number of accounts to generate
            start_key: Starting surrogate key value

        Returns:
            GeneratedData with account dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )

        self.logger.info(f"Generating {count} accounts")

        types, weights = zip(*self.ACCOUNT_TYPES)

        records = []
        keys = []
        now = datetime.now()

        for i in range(count):
            key = start_key + i
            keys.append(key)

            account_type = random.choices(types, weights=weights)[0]
            is_b2b = account_type in ("Business", "Corporate")

            company_name = None
            tax_id = None
            tax_exempt = False
            credit_limit = None

            if is_b2b:
                company_name = f"{self.faker.company()} {random.choice(self.COMPANY_SUFFIXES)}"
                tax_exempt = random.random() < 0.3
                if tax_exempt:
                    tax_id = self.faker.bothify("??-#######")
                credit_limit = Decimal(str(random.choice([5000, 10000, 25000, 50000, 100000, 250000])))

            if account_type == "Household":
                account_name = f"{self.faker.last_name()} Household"
            elif is_b2b:
                account_name = company_name
            elif account_type == "Guest":
                account_name = f"Guest-{key:06d}"
            else:
                account_name = f"{self.faker.first_name()} {self.faker.last_name()}"

            countries, c_weights = zip(*self.COUNTRIES)
            country = random.choices(countries, weights=c_weights)[0]
            state = self.faker.state_abbr() if country in ("USA", "Canada", "Australia") else None

            registration_date = self.faker.date_between(
                start_date=self.config.dates.start or "-3y",
                end_date=self.config.dates.end or "today"
            )

            account_status = random.choices(
                ["Active", "Suspended", "Closed", "Pending"],
                weights=[0.85, 0.05, 0.05, 0.05]
            )[0]

            closure_date = None
            is_active = account_status == "Active"
            if account_status == "Closed":
                closure_end = self.config.dates.end or "today"
                closure_date = self.faker.date_between(
                    start_date=registration_date,
                    end_date=closure_end
                )

            record = {
                "account_key": key,
                "account_id": f"ACCT{key:06d}",
                "account_name": account_name,
                "account_type": account_type,
                "company_name": company_name,
                "tax_id": tax_id,
                "tax_exempt_status": tax_exempt,
                "billing_address_line1": self.faker.street_address(),
                "billing_address_line2": self.faker.secondary_address() if random.random() < 0.2 else None,
                "billing_city": self.faker.city(),
                "billing_state": state,
                "billing_postal_code": self.faker.zipcode(),
                "billing_country": country,
                "payment_terms": random.choice(self.PAYMENT_TERMS[account_type]),
                "credit_limit": credit_limit,
                "account_status": account_status,
                "account_tier": random.choice(self.ACCOUNT_TIERS[account_type]),
                "registration_date": registration_date,
                "closure_date": closure_date,
                "is_active": is_active,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)

        df = self._create_dataframe(records)

        self.logger.info(f"Generated {len(records)} account records")

        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
