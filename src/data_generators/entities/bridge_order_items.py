"""
Bridge generator for bridge_order_items.

Generates order line item records linking sales to products.
"""

import random
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class BridgeOrderItemsGenerator(BaseEntityGenerator):
    """Generator for bridge_order_items table."""
    
    table_name = "bridge_order_items"
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        sale_keys: List[int] = None,
        product_keys: List[int] = None,
        min_items_per_order: int = 1,
        max_items_per_order: int = 5,
        **kwargs
    ) -> GeneratedData:
        """
        Generate order item records.
        
        Args:
            count: Ignored - items generated based on sales
            start_key: Starting surrogate key value
            sale_keys: List of sale keys to create items for
            product_keys: List of valid product keys
            min_items_per_order: Minimum items per order
            max_items_per_order: Maximum items per order
            
        Returns:
            GeneratedData with order item records
        """
        if not sale_keys:
            self.logger.warning("No sale keys provided for order items")
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating order items for {len(sale_keys)} sales")
        
        # Default product keys if not provided
        if not product_keys:
            product_keys = list(range(1, 501))
        
        records = []
        keys = []
        now = datetime.now()
        key = start_key
        
        for sale_key in sale_keys:
            # Determine number of items for this order
            num_items = random.randint(min_items_per_order, max_items_per_order)
            
            # Select unique products for this order
            order_products = random.sample(
                product_keys,
                min(num_items, len(product_keys))
            )
            
            for line_number, product_key in enumerate(order_products, 1):
                keys.append(key)
                
                # Generate item details
                quantity = random.randint(1, 3)
                unit_price = Decimal(str(round(random.uniform(9.99, 299.99), 2)))
                
                # Discount (20% chance)
                discount_amount = Decimal("0.00")
                if random.random() < 0.2:
                    discount_pct = random.uniform(0.05, 0.20)
                    discount_amount = round(unit_price * quantity * Decimal(str(discount_pct)), 2)
                
                line_total = (unit_price * quantity) - discount_amount
                
                record = {
                    "order_item_key": key,
                    "sale_key": sale_key,
                    "product_key": product_key,
                    "line_number": line_number,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": discount_amount,
                    "line_total": line_total,
                    "is_gift": random.random() < 0.05,  # 5% are gifts
                    "gift_message": self.faker.sentence() if random.random() < 0.05 else None,
                    "created_at": now,
                }
                records.append(record)
                key += 1
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} order item records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
