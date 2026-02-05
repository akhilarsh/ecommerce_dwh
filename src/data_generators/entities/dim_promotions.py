"""
Dimension generator for dim_promotions.

Generates promotion/campaign records.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData


class DimPromotionsGenerator(BaseEntityGenerator):
    """Generator for dim_promotions table."""
    
    table_name = "dim_promotions"
    
    PROMOTION_TYPES = [
        "Percentage Off",
        "Dollar Off",
        "BOGO",
        "Bundle Deal",
        "Clearance",
        "Seasonal Sale",
        "Flash Sale",
        "Member Exclusive",
    ]
    
    PROMOTION_PREFIXES = [
        "Spring", "Summer", "Fall", "Winter",
        "Holiday", "Weekend", "Flash", "Member",
        "Clearance", "Anniversary", "Birthday", "Special",
    ]
    
    PROMOTION_SUFFIXES = [
        "Sale", "Savings", "Deal", "Special",
        "Event", "Offer", "Promotion", "Discount",
    ]
    
    def generate(
        self,
        count: int = 20,
        start_key: int = 1,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate promotion dimension records.
        
        Args:
            count: Number of promotions to generate
            start_key: Starting surrogate key value
            start_date: Start of date range for promotions
            end_date: End of date range for promotions
            
        Returns:
            GeneratedData with promotion dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} promotions")
        
        start = start_date or datetime.combine(self.config.dates.start, datetime.min.time())
        end = end_date or datetime.combine(self.config.dates.end, datetime.min.time())
        
        records = []
        keys = []
        now = datetime.now()
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Generate promotion attributes
            promo_type = random.choice(self.PROMOTION_TYPES)
            promo_name = f"{random.choice(self.PROMOTION_PREFIXES)} {random.choice(self.PROMOTION_SUFFIXES)}"
            
            # Generate dates within range
            promo_start = self.faker.date_time_between(start_date=start, end_date=end)
            duration = random.randint(3, 30)  # 3-30 day promotions
            promo_end = promo_start + timedelta(days=duration)
            
            # Generate discount
            if promo_type == "Percentage Off":
                discount_pct = Decimal(str(random.randint(10, 50) / 100))
                discount_amt = None
            elif promo_type == "Dollar Off":
                discount_pct = None
                discount_amt = Decimal(str(random.randint(5, 50)))
            else:
                discount_pct = Decimal(str(random.randint(10, 30) / 100))
                discount_amt = None
            
            # Max discount (None means no max)
            max_discount_choices = [None, 50, 100, 200]
            max_discount_choice = random.choice(max_discount_choices)
            max_discount_amount = None
            if discount_pct and max_discount_choice is not None:
                max_discount_amount = Decimal(str(max_discount_choice))
            
            record = {
                "promotion_key": key,
                "promotion_id": f"PROMO{key:05d}",
                "promotion_name": promo_name,
                "promotion_type": promo_type,
                "promotion_code": f"{random.choice(self.PROMOTION_PREFIXES)[:3].upper()}{key:03d}",
                "start_date": promo_start.date(),
                "end_date": promo_end.date(),
                "discount_percentage": discount_pct,
                "discount_amount": discount_amt,
                "min_purchase_amount": Decimal(str(random.choice([0, 25, 50, 100]))),
                "max_discount_amount": max_discount_amount,
                "is_stackable": random.random() < 0.2,  # 20% stackable
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} promotion records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
