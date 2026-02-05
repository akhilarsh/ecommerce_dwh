"""
Dimension generator for dim_customer_segments.

Generates customer segment records for customer segmentation.
"""

from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimCustomerSegmentsGenerator(BaseEntityGenerator):
    """Generator for dim_customer_segments table."""
    
    table_name = "dim_customer_segments"
    
    # Standard customer segments
    SEGMENTS = [
        {
            "segment_name": "VIP",
            "segment_code": "VIP",
            "description": "High-value customers with premium benefits",
            "min_lifetime_value": 5000.00,
            "max_lifetime_value": None,
            "is_active": True,
        },
        {
            "segment_name": "Loyal",
            "segment_code": "LOYAL",
            "description": "Repeat customers with consistent purchase history",
            "min_lifetime_value": 1000.00,
            "max_lifetime_value": 4999.99,
            "is_active": True,
        },
        {
            "segment_name": "Regular",
            "segment_code": "REG",
            "description": "Regular customers with moderate purchase frequency",
            "min_lifetime_value": 250.00,
            "max_lifetime_value": 999.99,
            "is_active": True,
        },
        {
            "segment_name": "New",
            "segment_code": "NEW",
            "description": "Recently acquired customers (first 90 days)",
            "min_lifetime_value": 0.00,
            "max_lifetime_value": 249.99,
            "is_active": True,
        },
        {
            "segment_name": "At Risk",
            "segment_code": "RISK",
            "description": "Previously active customers showing decreased engagement",
            "min_lifetime_value": None,
            "max_lifetime_value": None,
            "is_active": True,
        },
        {
            "segment_name": "Dormant",
            "segment_code": "DORM",
            "description": "Inactive customers (no purchase in 180+ days)",
            "min_lifetime_value": None,
            "max_lifetime_value": None,
            "is_active": True,
        },
        {
            "segment_name": "Churned",
            "segment_code": "CHURN",
            "description": "Lost customers (no purchase in 365+ days)",
            "min_lifetime_value": None,
            "max_lifetime_value": None,
            "is_active": True,
        },
    ]
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate customer segment dimension records.
        
        Args:
            count: Ignored - all standard segments are generated
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with customer segment dimension records
        """
        self.logger.info("Generating customer segment dimension")
        
        records = []
        keys = []
        now = datetime.now()
        
        for i, segment in enumerate(self.SEGMENTS):
            key = start_key + i
            keys.append(key)
            
            record = {
                "segment_key": key,
                "segment_id": f"SEG{key:03d}",
                **segment,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} customer segment records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
