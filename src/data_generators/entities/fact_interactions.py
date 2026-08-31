"""
Fact generator for fact_customer_interactions.

Generates customer interaction/touchpoint records.
"""

import base64
import json
import os
import random
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import date_to_key, generate_date_range_keys


class FactCustomerInteractionsGenerator(BaseEntityGenerator):
    """Generator for fact_customer_interactions table."""
    
    table_name = "fact_customer_interactions"
    
    INTERACTION_TYPES = [
        "Page View",
        "Product View",
        "Add to Cart",
        "Remove from Cart",
        "Wishlist Add",
        "Search",
        "Store Visit",
        "Customer Service Call",
        "Email Open",
        "Email Click",
        "App Session",
    ]
    
    DEVICES = ["Desktop", "Mobile", "Tablet", "In-Store Kiosk", "Phone"]

    _WORLD_LON_RANGE = (-180.0, 180.0)
    _WORLD_LAT_RANGE = (-90.0, 90.0)
    
    def generate(
        self,
        count: int = 2500,
        start_key: int = 1,
        dimension_keys: Dict[str, List[int]] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sale_keys: List[int] = None,
        customer_selector=None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate customer interaction records.
        
        Args:
            count: Number of interactions to generate
            start_key: Starting surrogate key value
            dimension_keys: Dictionary of dimension table -> valid keys
            target_date: Specific date for interactions (single date)
            start_date: Start of date range for interactions
            end_date: End of date range for interactions
            sale_keys: List of sale keys for interactions leading to purchase
            customer_selector: CustomerSelector for ratio-based selection
            
        Returns:
            GeneratedData with customer interaction records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} customer interactions")
        
        # Default dimension keys if not provided
        dimension_keys = dimension_keys or {}
        
        records = []
        keys = []
        now = datetime.now()
        
        # Get dimension key lists with defaults
        customer_keys = dimension_keys.get("dim_customers", list(range(1, 1001)))
        channel_keys = dimension_keys.get("dim_channels", list(range(1, 7)))
        store_keys = dimension_keys.get("dim_stores", list(range(1, 11)))
        date_keys = dimension_keys.get("dim_dates", [])
        time_keys = dimension_keys.get("dim_time", list(range(0, 240000, 1500)))
        employee_keys = dimension_keys.get("dim_employees", list(range(1, 51)))
        product_keys = dimension_keys.get("dim_products", list(range(1, 501)))
        
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
            
            # Interaction type
            interaction_type = random.choices(
                self.INTERACTION_TYPES,
                weights=[0.25, 0.20, 0.10, 0.05, 0.05, 0.10, 0.08, 0.05, 0.05, 0.04, 0.03]
            )[0]
            
            # Store interaction - only for physical interactions
            store_key = None
            employee_key = None
            if interaction_type in ["Store Visit", "Customer Service Call"]:
                store_key = random.choice(store_keys)
                if random.random() < 0.5:
                    employee_key = random.choice(employee_keys)
            
            # Product context
            product_key = None
            if interaction_type in ["Product View", "Add to Cart", "Remove from Cart", "Wishlist Add"]:
                product_key = random.choice(product_keys)
            
            # Link to sale (10% chance for Add to Cart)
            sale_key = None
            if interaction_type == "Add to Cart" and sale_keys and random.random() < 0.3:
                sale_key = random.choice(sale_keys)
            
            # Duration based on interaction type
            duration_seconds = self._get_duration(interaction_type)
            
            record = {
                "interaction_key": key,
                "interaction_id": f"INT{key:09d}",
                "date_key": date_key,
                "time_key": random.choice(time_keys),
                "customer_key": customer_key,
                "channel_key": random.choice(channel_keys),
                "store_key": store_key,
                "employee_key": employee_key,
                "product_key": product_key,
                "sale_key": sale_key,
                "interaction_type": interaction_type,
                "device_type": random.choice(self.DEVICES),
                "session_id": f"SES{self.faker.uuid4()[:8].upper()}",
                "page_url": self._generate_url(interaction_type) if interaction_type != "Store Visit" else None,
                "duration_seconds": duration_seconds,
                "is_converted": sale_key is not None,
                "created_at": now,
                "event_properties": json.dumps({
                    "ab_variant": random.choice(["control", "variant_a", "variant_b"]),
                    "referrer": random.choice(["google", "email", "direct", "social", None]),
                    "viewport_width": random.randint(320, 2560),
                    "scroll_depth": round(random.uniform(0.0, 1.0), 2),
                }),
                "geo_location": (
                    f"POINT({round(random.uniform(*self._WORLD_LON_RANGE), 4)} "
                    f"{round(random.uniform(*self._WORLD_LAT_RANGE), 4)})"
                ),
                # Random byte payload, base64-encoded for safe CSV transport.
                # Loaders are responsible for decoding (Databricks: unbase64()).
                "raw_payload": base64.b64encode(
                    random.randbytes(random.randint(16, 64))
                ).decode("ascii"),
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} customer interaction records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _get_duration(self, interaction_type: str) -> int:
        """Get duration in seconds based on interaction type."""
        durations = {
            "Page View": (5, 120),
            "Product View": (10, 300),
            "Add to Cart": (2, 10),
            "Remove from Cart": (2, 5),
            "Wishlist Add": (2, 10),
            "Search": (5, 30),
            "Store Visit": (300, 3600),
            "Customer Service Call": (60, 1800),
            "Email Open": (5, 60),
            "Email Click": (2, 10),
            "App Session": (30, 600),
        }
        min_dur, max_dur = durations.get(interaction_type, (5, 60))
        return random.randint(min_dur, max_dur)
    
    def _generate_url(self, interaction_type: str) -> str:
        """Generate a plausible URL based on interaction type."""
        base = "https://www.store.com"
        urls = {
            "Page View": f"{base}/browse",
            "Product View": f"{base}/products/{random.randint(1000, 9999)}",
            "Add to Cart": f"{base}/cart/add",
            "Remove from Cart": f"{base}/cart/remove",
            "Wishlist Add": f"{base}/wishlist/add",
            "Search": f"{base}/search?q={self.faker.word()}",
            "Email Open": f"{base}/email/view/{self.faker.uuid4()[:8]}",
            "Email Click": f"{base}/email/click/{self.faker.uuid4()[:8]}",
            "App Session": f"{base}/app/home",
        }
        return urls.get(interaction_type, base)
