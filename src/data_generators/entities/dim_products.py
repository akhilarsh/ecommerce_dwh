"""
Dimension generator for dim_products.

Generates product catalog records with SCD Type 2 support.
"""

import random
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimProductsGenerator(BaseEntityGenerator):
    """Generator for dim_products table (SCD Type 2)."""
    
    table_name = "dim_products"
    
    # Product name components by category
    PRODUCT_ADJECTIVES = [
        "Premium", "Classic", "Ultra", "Pro", "Essential",
        "Deluxe", "Elite", "Advanced", "Basic", "Compact",
    ]
    
    PRODUCT_TYPES = {
        "Electronics": ["Laptop", "Phone", "Tablet", "Headphones", "Speaker", "Camera"],
        "Clothing": ["Shirt", "Pants", "Jacket", "Dress", "Shoes", "Hat"],
        "Home": ["Chair", "Table", "Lamp", "Rug", "Mirror", "Shelf"],
        "Sports": ["Ball", "Racket", "Helmet", "Gloves", "Shoes", "Bag"],
        "Beauty": ["Cream", "Serum", "Mask", "Oil", "Spray", "Balm"],
    }
    
    BRANDS = [
        "NovaTech", "StyleCraft", "HomeBase", "SportMax", "GlowUp",
        "TechPro", "UrbanWear", "CozyLiving", "ActiveLife", "PureSkin",
        "PrimeGear", "FashionFwd", "ModernHome", "FitNation", "BeautyBliss",
    ]
    
    def generate(
        self,
        count: int = 500,
        start_key: int = 1,
        category_keys: List[int] = None,
        effective_date: date = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate product dimension records.
        
        Args:
            count: Number of products to generate
            start_key: Starting surrogate key value
            category_keys: List of valid category keys
            effective_date: SCD effective date (defaults to config start date)
            
        Returns:
            GeneratedData with product dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} products")
        
        # Default category keys if not provided
        if not category_keys:
            category_keys = list(range(1, 101))  # Assume 100 categories
        
        # Use config date or provided date
        eff_date = effective_date or self.config.dates.start
        end_date = date(9999, 12, 31)
        
        records = []
        keys = []
        now = datetime.now()
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Generate product attributes
            category_type = random.choice(list(self.PRODUCT_TYPES.keys()))
            product_type = random.choice(self.PRODUCT_TYPES[category_type])
            adjective = random.choice(self.PRODUCT_ADJECTIVES)
            brand = random.choice(self.BRANDS)
            
            product_name = f"{brand} {adjective} {product_type}"
            
            # Generate pricing
            base_price = Decimal(str(round(random.uniform(9.99, 999.99), 2)))
            cost = base_price * Decimal(str(round(random.uniform(0.3, 0.7), 2)))
            
            # Generate SKU
            sku = f"{brand[:3].upper()}-{product_type[:3].upper()}-{key:05d}"
            
            record = {
                "product_key": key,
                "product_id": f"PROD{key:06d}",
                "sku": sku,
                "product_name": product_name,
                "brand": brand,
                "category_key": random.choice(category_keys),
                "description": f"High-quality {product_type.lower()} from {brand}",
                "unit_price": base_price,
                "unit_cost": round(cost, 2),
                "weight_kg": Decimal(str(round(random.uniform(0.1, 20.0), 2))),
                "is_active": True,
                "is_discontinued": False,
                # SCD Type 2 columns
                "effective_date": eff_date,
                "end_date": end_date,
                "is_current": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} product records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
