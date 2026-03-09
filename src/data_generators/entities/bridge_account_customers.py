"""
Bridge generator for bridge_account_customers.

Links accounts to customers with role assignments.
"""

import random
from datetime import datetime, date
from typing import Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class BridgeAccountCustomersGenerator(BaseEntityGenerator):
    """Generator for bridge_account_customers table."""

    table_name = "bridge_account_customers"

    ROLES_BY_TYPE = {
        "Individual": ["Owner"],
        "Household": ["Owner", "Member"],
        "Business": ["Owner", "Admin", "Buyer", "Viewer"],
        "Corporate": ["Owner", "Admin", "Buyer", "Viewer"],
        "Guest": ["Owner"],
    }

    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        account_customer_map: Optional[Dict[int, List[int]]] = None,
        account_types: Optional[Dict[int, str]] = None,
        effective_date: Optional[date] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate account-customer bridge records.

        Args:
            count: Ignored -- records driven by account_customer_map
            start_key: Starting surrogate key value
            account_customer_map: {account_key: [customer_key, ...]}
            account_types: {account_key: account_type} for role assignment
            effective_date: Default effective date for relationships

        Returns:
            GeneratedData with bridge records
        """
        if not account_customer_map:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )

        self.logger.info(
            f"Generating account-customer links for {len(account_customer_map)} accounts"
        )

        eff_date = effective_date or self.config.dates.start or date(2025, 1, 1)
        now = datetime.now()

        records = []
        keys = []
        key = start_key

        for account_key, customer_keys in account_customer_map.items():
            acct_type = (account_types or {}).get(account_key, "Individual")
            available_roles = self.ROLES_BY_TYPE.get(acct_type, ["Owner"])

            for idx, customer_key in enumerate(customer_keys):
                keys.append(key)

                if idx == 0:
                    role = "Owner"
                    is_primary = True
                else:
                    role = random.choice(available_roles)
                    is_primary = False

                record = {
                    "account_customer_key": key,
                    "account_key": account_key,
                    "customer_key": customer_key,
                    "role": role,
                    "is_primary_contact": is_primary,
                    "effective_date": eff_date,
                    "end_date": None,
                    "is_current": True,
                    "created_at": now,
                }
                records.append(record)
                key += 1

        df = self._create_dataframe(records)

        self.logger.info(f"Generated {len(records)} account-customer bridge records")

        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
