"""
Fact generator for fact_loyalty_points.

Generates loyalty program transaction records.
"""

import random
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import date_to_key, generate_date_range_keys


class FactLoyaltyPointsGenerator(BaseEntityGenerator):
    """Generator for fact_loyalty_points table."""
    
    table_name = "fact_loyalty_points"
    
    TRANSACTION_TYPES = [
        "Earned - Purchase",
        "Earned - Bonus",
        "Earned - Referral",
        "Earned - Birthday",
        "Earned - Signup",
        "Redeemed - Discount",
        "Redeemed - Free Item",
        "Redeemed - Shipping",
        "Expired",
        "Adjustment",
    ]
    
    def generate(
        self,
        count: int = 1000,
        start_key: int = 1,
        dimension_keys: Dict[str, List[int]] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sale_keys: List[int] = None,
        loyalty_customer_keys: List[int] = None,
        customer_selector=None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate loyalty points transaction records.
        
        Args:
            count: Number of transactions to generate
            start_key: Starting surrogate key value
            dimension_keys: Dictionary of dimension table -> valid keys
            target_date: Specific date for transactions (single date)
            start_date: Start of date range for transactions
            end_date: End of date range for transactions
            sale_keys: List of sale keys for earned points
            loyalty_customer_keys: List of customer keys who are loyalty members
            customer_selector: CustomerSelector for ratio-based selection
            
        Returns:
            GeneratedData with loyalty points transaction records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} loyalty transactions")
        
        # Default dimension keys if not provided
        dimension_keys = dimension_keys or {}
        
        records = []
        keys = []
        now = datetime.now()
        
        # Get dimension key lists with defaults
        customer_keys = loyalty_customer_keys or dimension_keys.get("dim_customers", list(range(1, 1001)))
        channel_keys = dimension_keys.get("dim_channels", list(range(1, 7)))
        date_keys = dimension_keys.get("dim_dates", [])
        time_keys = dimension_keys.get("dim_time", list(range(0, 240000, 1500)))
        
        # Inclusive date keys for range-based generation (both bounds included)
        range_date_keys: List[int] = []
        if not target_date:
            if start_date and end_date:
                if start_date > end_date:
                    raise ValueError(
                        f"start_date {start_date} is after end_date {end_date}"
                    )
                range_date_keys = generate_date_range_keys(start_date, end_date)
            elif not date_keys:
                config_start = self.config.dates.start or date(2024, 1, 1)
                config_end = self.config.dates.end or date(2024, 12, 31)
                if config_start > config_end:
                    raise ValueError(
                        f"config date range start {config_start} is after "
                        f"end {config_end}"
                    )
                range_date_keys = generate_date_range_keys(config_start, config_end)
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Select customer (using selector if provided, else random from loyalty members)
            if customer_selector and customer_selector.has_keys():
                customer_key = customer_selector.select()
            else:
                customer_key = random.choice(customer_keys)
            
            # Select date - specific, range, or config default
            if target_date:
                date_key = date_to_key(target_date)
            elif range_date_keys:
                date_key = random.choice(range_date_keys)
            else:
                date_key = random.choice(date_keys)
            
            # Transaction type - weighted toward earnings
            transaction_type = random.choices(
                self.TRANSACTION_TYPES,
                weights=[0.50, 0.10, 0.05, 0.02, 0.03, 0.15, 0.05, 0.05, 0.03, 0.02]
            )[0]
            
            # Points based on transaction type
            if transaction_type.startswith("Earned"):
                points = self._get_earned_points(transaction_type)
            elif transaction_type.startswith("Redeemed"):
                points = -self._get_redeemed_points(transaction_type)
            elif transaction_type == "Expired":
                points = -random.randint(50, 500)
            else:  # Adjustment
                points = random.randint(-100, 100)
            
            # Link to sale for purchase-based earnings
            sale_key = None
            if transaction_type == "Earned - Purchase" and sale_keys:
                sale_key = random.choice(sale_keys)
            
            record = {
                "loyalty_transaction_key": key,
                "transaction_id": f"LYL{key:09d}",
                "date_key": date_key,
                "time_key": random.choice(time_keys),
                "customer_key": customer_key,
                "sale_key": sale_key,
                "channel_key": random.choice(channel_keys),
                "transaction_type": transaction_type,
                "points": points,
                "points_balance_after": random.randint(0, 50000),  # Would be calculated in real ETL
                "description": self._get_description(transaction_type, points),
                "expiration_date": self._get_expiration_date(date_key, transaction_type),
                "created_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} loyalty transaction records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _get_earned_points(self, transaction_type: str) -> int:
        """Get points earned based on transaction type."""
        points_ranges = {
            "Earned - Purchase": (10, 500),
            "Earned - Bonus": (50, 200),
            "Earned - Referral": (100, 500),
            "Earned - Birthday": (100, 100),
            "Earned - Signup": (50, 50),
        }
        min_pts, max_pts = points_ranges.get(transaction_type, (10, 100))
        return random.randint(min_pts, max_pts)
    
    def _get_redeemed_points(self, transaction_type: str) -> int:
        """Get points redeemed based on transaction type."""
        points_ranges = {
            "Redeemed - Discount": (100, 1000),
            "Redeemed - Free Item": (500, 2000),
            "Redeemed - Shipping": (50, 200),
        }
        min_pts, max_pts = points_ranges.get(transaction_type, (100, 500))
        return random.randint(min_pts, max_pts)
    
    def _get_description(self, transaction_type: str, points: int) -> str:
        """Generate description for the transaction."""
        abs_points = abs(points)
        if transaction_type == "Earned - Purchase":
            return f"Earned {abs_points} points on purchase"
        elif transaction_type == "Earned - Bonus":
            return f"Bonus points promotion: {abs_points} points"
        elif transaction_type == "Earned - Referral":
            return f"Referral reward: {abs_points} points"
        elif transaction_type == "Earned - Birthday":
            return f"Birthday bonus: {abs_points} points"
        elif transaction_type == "Earned - Signup":
            return f"Welcome bonus: {abs_points} points"
        elif transaction_type == "Redeemed - Discount":
            return f"Redeemed {abs_points} points for discount"
        elif transaction_type == "Redeemed - Free Item":
            return f"Redeemed {abs_points} points for free item"
        elif transaction_type == "Redeemed - Shipping":
            return f"Redeemed {abs_points} points for free shipping"
        elif transaction_type == "Expired":
            return f"Points expired: {abs_points} points"
        else:
            return f"Points adjustment: {points} points"
    
    def _get_expiration_date(self, date_key: int, transaction_type: str) -> Optional[date]:
        """Calculate expiration date for earned points (1 year from earn date)."""
        if not transaction_type.startswith("Earned"):
            return None
        
        from datetime import timedelta
        from ..utils.date_keys import key_to_date
        
        try:
            earn_date = key_to_date(date_key)
            return earn_date + timedelta(days=365)
        except (ValueError, TypeError):
            # If date_key is invalid, return None
            return None
