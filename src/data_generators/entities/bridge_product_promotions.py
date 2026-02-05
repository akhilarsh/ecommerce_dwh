"""
Bridge generator for bridge_product_promotions.

Generates product-promotion association records.
"""

import random
from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class BridgeProductPromotionsGenerator(BaseEntityGenerator):
    """Generator for bridge_product_promotions table."""
    
    table_name = "bridge_product_promotions"
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        promotion_keys: List[int] = None,
        product_keys: List[int] = None,
        products_per_promotion_min: int = 5,
        products_per_promotion_max: int = 50,
        **kwargs
    ) -> GeneratedData:
        """
        Generate product-promotion association records.
        
        Args:
            count: Ignored - associations generated based on promotions
            start_key: Starting surrogate key value
            promotion_keys: List of promotion keys
            product_keys: List of valid product keys
            products_per_promotion_min: Min products per promotion
            products_per_promotion_max: Max products per promotion
            
        Returns:
            GeneratedData with product-promotion records
        """
        if not promotion_keys:
            self.logger.warning("No promotion keys provided")
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating product-promotion links for {len(promotion_keys)} promotions")
        
        # Default product keys if not provided
        if not product_keys:
            product_keys = list(range(1, 501))
        
        records = []
        keys = []
        now = datetime.now()
        key = start_key
        
        for promotion_key in promotion_keys:
            # Determine number of products for this promotion
            max_products = min(products_per_promotion_max, len(product_keys))
            min_products = min(products_per_promotion_min, max_products)
            
            if max_products <= 0:
                continue
            
            num_products = random.randint(min_products, max_products)
            
            # Select random products for this promotion
            promo_products = random.sample(product_keys, num_products)
            
            for product_key in promo_products:
                keys.append(key)
                
                record = {
                    "product_promotion_key": key,
                    "product_key": product_key,
                    "promotion_key": promotion_key,
                    "is_featured": random.random() < 0.1,  # 10% are featured
                    "priority": random.randint(1, 10),
                    "created_at": now,
                }
                records.append(record)
                key += 1
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} product-promotion records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
