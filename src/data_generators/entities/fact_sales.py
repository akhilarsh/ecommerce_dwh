"""
Fact generator for fact_sales.

Generates sales transaction records with proper referential integrity.
"""

import json
import random
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import date_to_key, generate_date_range_keys


class FactSalesGenerator(BaseEntityGenerator):
    """Generator for fact_sales table."""
    
    table_name = "fact_sales"
    
    ORDER_TAG_POOL = [
        "express", "gift", "fragile", "bulk", "subscription", "loyalty-redeem",
        "first-order", "returns-eligible", "digital", "pre-order",
    ]
    CARRIER_CODES = ["UPS", "FEDEX", "USPS", "DHL", "ONTRAC"]

    ORDER_STATUSES = [
        "Completed",
        "Processing",
        "Shipped",
        "Delivered",
        "Cancelled",
        "Returned",
    ]
    
    def generate(
        self,
        count: int = 5000,
        start_key: int = 1,
        dimension_keys: Dict[str, List[int]] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_selector=None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate sales fact records.
        
        Args:
            count: Number of sales to generate
            start_key: Starting surrogate key value
            dimension_keys: Dictionary of dimension table -> valid keys
            target_date: Specific date for sales (single date)
            start_date: Start of date range for sales
            end_date: End of date range for sales
            customer_selector: CustomerSelector for ratio-based selection
            
        Returns:
            GeneratedData with sales fact records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} sales")
        
        # Default dimension keys if not provided
        dimension_keys = dimension_keys or {}
        
        records = []
        keys = []
        now = datetime.now()
        
        # Get dimension key lists with defaults
        customer_keys = dimension_keys.get("dim_customers", list(range(1, 1001)))
        store_keys = dimension_keys.get("dim_stores", list(range(1, 11)))
        channel_keys = dimension_keys.get("dim_channels", list(range(1, 7)))
        date_keys = dimension_keys.get("dim_dates", [])
        time_keys = dimension_keys.get("dim_time", list(range(0, 240000, 1500)))
        promotion_keys = dimension_keys.get("dim_promotions", list(range(1, 21)))
        payment_method_keys = dimension_keys.get("dim_payment_methods", list(range(1, 11)))
        shipping_method_keys = dimension_keys.get("dim_shipping_methods", list(range(1, 9)))
        employee_keys = dimension_keys.get("dim_employees", list(range(1, 51)))
        
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
                range_date_keys = generate_date_range_keys(
                    self.config.dates.start or date(2024, 1, 1),
                    self.config.dates.end or date(2024, 12, 31)
                )
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Select customer (using selector if provided, else random)
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
            
            # Generate order details
            order_status = random.choices(
                self.ORDER_STATUSES,
                weights=[0.75, 0.05, 0.05, 0.05, 0.05, 0.05]
            )[0]
            
            # Amount generation
            gross_amount = Decimal(str(round(random.uniform(10, 500), 2)))
            discount_amount = Decimal("0.00")
            
            # Apply promotion (30% chance)
            promotion_key = None
            if random.random() < 0.3:
                promotion_key = random.choice(promotion_keys)
                discount_pct = random.uniform(0.05, 0.25)
                discount_amount = round(gross_amount * Decimal(str(discount_pct)), 2)
            
            net_amount = gross_amount - discount_amount
            tax_rate = Decimal("0.0825")  # 8.25% tax
            tax_amount = round(net_amount * tax_rate, 2)
            total_amount = net_amount + tax_amount
            
            # Shipping
            shipping_method_key = random.choice(shipping_method_keys)
            shipping_amount = Decimal(str(round(random.uniform(0, 15), 2)))
            
            record = {
                "sale_key": key,
                "order_id": f"ORD{key:08d}",
                "date_key": date_key,
                "time_key": random.choice(time_keys),
                "customer_key": customer_key,
                "store_key": random.choice(store_keys),
                "channel_key": random.choice(channel_keys),
                "promotion_key": promotion_key,
                "payment_method_key": random.choice(payment_method_keys),
                "shipping_method_key": shipping_method_key,
                "employee_key": random.choice(employee_keys) if random.random() < 0.5 else None,
                "quantity": random.randint(1, 5),
                "gross_amount": gross_amount,
                "discount_amount": discount_amount,
                "net_amount": net_amount,
                "tax_amount": tax_amount,
                "shipping_amount": shipping_amount,
                "total_amount": total_amount + shipping_amount,
                "order_status": order_status,
                "is_online": random.random() < 0.6,
                "created_at": now,
                "order_tags": json.dumps(
                    random.sample(self.ORDER_TAG_POOL, k=random.randint(1, 3))
                ),
                "shipment_metadata": json.dumps({
                    "carrier": random.choice(self.CARRIER_CODES),
                    "tracking_number": f"1Z{key:015d}",
                    "weight_kg": round(random.uniform(0.1, 20.0), 2),
                    "insurance": random.random() < 0.2,
                }),
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} sales records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
