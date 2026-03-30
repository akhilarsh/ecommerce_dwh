"""
Fact generator for fact_inventory_snapshots.

Generates daily inventory snapshot records.
"""

import random
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import date_to_key, key_to_date


class FactInventorySnapshotsGenerator(BaseEntityGenerator):
    """Generator for fact_inventory_snapshots table."""
    
    table_name = "fact_inventory_snapshots"
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        dimension_keys: Dict[str, List[int]] = None,
        snapshot_date: Optional[date] = None,
        days: int = 30,
        **kwargs
    ) -> GeneratedData:
        """
        Generate inventory snapshot records.
        
        Args:
            count: Ignored - records generated based on products * stores * days
            start_key: Starting surrogate key value
            dimension_keys: Dictionary of dimension table -> valid keys
            snapshot_date: Specific date for snapshot (for daily snapshots)
            days: Number of days of history (for initial load)
            
        Returns:
            GeneratedData with inventory snapshot records
        """
        self.logger.info("Generating inventory snapshots")
        
        # Default dimension keys if not provided
        dimension_keys = dimension_keys or {}
        
        product_keys = dimension_keys.get("dim_products", list(range(1, 501)))
        store_keys = dimension_keys.get("dim_stores", list(range(1, 11)))
        date_keys = dimension_keys.get("dim_dates", [])
        
        records = []
        keys = []
        now = datetime.now()
        key = start_key
        
        if snapshot_date:
            # Single day snapshot
            dates_to_process = [snapshot_date]
        else:
            # Generate for date range
            if date_keys:
                # Filter to valid YYYYMMDD keys (8-digit integers) and take last N days
                valid_date_keys = [dk for dk in date_keys if 19000101 <= dk <= 99991231]
                selected_keys = sorted(valid_date_keys)[-days:]
                dates_to_process = [key_to_date(dk) for dk in selected_keys]
            else:
                # Generate dates from config
                from datetime import timedelta
                end = self.config.dates.end
                dates_to_process = [
                    end - timedelta(days=i) for i in range(days)
                ]
        
        for d in dates_to_process:
            date_key = date_to_key(d)
            
            for store_key in store_keys:
                for product_key in product_keys:
                    keys.append(key)
                    
                    # Generate inventory levels
                    quantity_on_hand = random.randint(0, 500)
                    quantity_reserved = random.randint(0, min(50, quantity_on_hand))
                    quantity_available = quantity_on_hand - quantity_reserved
                    
                    # Reorder point and status
                    reorder_point = random.randint(20, 100)
                    is_below_reorder = quantity_available < reorder_point
                    
                    record = {
                        "inventory_snapshot_key": key,
                        "date_key": date_key,
                        "product_key": product_key,
                        "store_key": store_key,
                        "quantity_on_hand": quantity_on_hand,
                        "quantity_reserved": quantity_reserved,
                        "quantity_available": quantity_available,
                        "reorder_point": reorder_point,
                        "is_below_reorder_point": is_below_reorder,
                        "days_of_supply": random.randint(1, 90) if quantity_on_hand > 0 else 0,
                        "created_at": now,
                    }
                    records.append(record)
                    key += 1
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} inventory snapshot records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
