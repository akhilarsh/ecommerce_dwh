"""
Dimension generator for dim_shipping_methods.

Generates shipping/fulfillment method records.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimShippingMethodsGenerator(BaseEntityGenerator):
    """Generator for dim_shipping_methods table."""
    
    table_name = "dim_shipping_methods"
    
    # Standard shipping methods
    SHIPPING_METHODS = [
        {
            "shipping_method_name": "Standard Shipping",
            "shipping_method_code": "STD",
            "carrier": "USPS",
            "estimated_days_min": 5,
            "estimated_days_max": 7,
            "base_cost": Decimal("5.99"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Express Shipping",
            "shipping_method_code": "EXP",
            "carrier": "UPS",
            "estimated_days_min": 2,
            "estimated_days_max": 3,
            "base_cost": Decimal("12.99"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Next Day Air",
            "shipping_method_code": "NDA",
            "carrier": "FedEx",
            "estimated_days_min": 1,
            "estimated_days_max": 1,
            "base_cost": Decimal("24.99"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Store Pickup",
            "shipping_method_code": "PICKUP",
            "carrier": "Store",
            "estimated_days_min": 0,
            "estimated_days_max": 1,
            "base_cost": Decimal("0.00"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Curbside Pickup",
            "shipping_method_code": "CURB",
            "carrier": "Store",
            "estimated_days_min": 0,
            "estimated_days_max": 1,
            "base_cost": Decimal("0.00"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Same Day Delivery",
            "shipping_method_code": "SAME",
            "carrier": "Local Courier",
            "estimated_days_min": 0,
            "estimated_days_max": 0,
            "base_cost": Decimal("14.99"),
            "is_active": True,
        },
        {
            "shipping_method_name": "Economy Shipping",
            "shipping_method_code": "ECON",
            "carrier": "USPS",
            "estimated_days_min": 7,
            "estimated_days_max": 10,
            "base_cost": Decimal("3.99"),
            "is_active": True,
        },
        {
            "shipping_method_name": "International Standard",
            "shipping_method_code": "INTL",
            "carrier": "DHL",
            "estimated_days_min": 10,
            "estimated_days_max": 21,
            "base_cost": Decimal("19.99"),
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
        Generate shipping method dimension records.
        
        Args:
            count: Ignored - all standard shipping methods are generated
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with shipping method dimension records
        """
        self.logger.info("Generating shipping method dimension")
        
        records = []
        keys = []
        now = datetime.now()
        
        for i, method in enumerate(self.SHIPPING_METHODS):
            key = start_key + i
            keys.append(key)
            
            record = {
                "shipping_method_key": key,
                "shipping_method_id": f"SM{key:03d}",
                **method,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} shipping method records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
