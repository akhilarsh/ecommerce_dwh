"""
Dimension generator for dim_product_categories.

Generates product category hierarchy records.
"""

from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimProductCategoriesGenerator(BaseEntityGenerator):
    """Generator for dim_product_categories table."""
    
    table_name = "dim_product_categories"
    
    # Product category hierarchy
    CATEGORY_HIERARCHY = {
        "Electronics": {
            "Computers": ["Laptops", "Desktops", "Tablets"],
            "Mobile": ["Smartphones", "Accessories"],
            "Audio": ["Headphones", "Speakers", "Home Audio"],
            "Gaming": ["Consoles", "PC Gaming", "Games"],
        },
        "Clothing": {
            "Men's": ["Shirts", "Pants", "Outerwear", "Shoes"],
            "Women's": ["Tops", "Bottoms", "Dresses", "Shoes"],
            "Kids'": ["Boys", "Girls", "Baby"],
        },
        "Home & Garden": {
            "Furniture": ["Living Room", "Bedroom", "Office"],
            "Kitchen": ["Appliances", "Cookware", "Dining"],
            "Garden": ["Plants", "Tools", "Outdoor Living"],
        },
        "Sports & Outdoors": {
            "Exercise": ["Cardio", "Strength", "Yoga"],
            "Team Sports": ["Basketball", "Soccer", "Baseball"],
            "Outdoor": ["Camping", "Hiking", "Cycling"],
        },
        "Beauty & Health": {
            "Skincare": ["Face", "Body", "Sun Care"],
            "Makeup": ["Face", "Eyes", "Lips"],
            "Hair Care": ["Shampoo", "Styling", "Treatments"],
        },
    }
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate product category dimension records.
        
        Args:
            count: Ignored - all categories in hierarchy are generated
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with product category dimension records
        """
        self.logger.info("Generating product category dimension")
        
        records = []
        keys = []
        now = datetime.now()
        key = start_key
        
        # Track parent keys for hierarchy
        category_keys = {}
        
        for category, subcategories in self.CATEGORY_HIERARCHY.items():
            # Level 1: Category
            category_key = key
            category_keys[category] = category_key
            keys.append(key)
            
            records.append({
                "category_key": key,
                "category_id": f"CAT{key:04d}",
                "category_name": category,
                "category_level": 1,
                "parent_category_key": None,
                "category_path": category,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            key += 1
            
            for subcategory, brands in subcategories.items():
                # Level 2: Subcategory
                subcategory_key = key
                keys.append(key)
                
                records.append({
                    "category_key": key,
                    "category_id": f"CAT{key:04d}",
                    "category_name": subcategory,
                    "category_level": 2,
                    "parent_category_key": category_key,
                    "category_path": f"{category} > {subcategory}",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
                key += 1
                
                for brand in brands:
                    # Level 3: Brand/Type
                    keys.append(key)
                    
                    records.append({
                        "category_key": key,
                        "category_id": f"CAT{key:04d}",
                        "category_name": brand,
                        "category_level": 3,
                        "parent_category_key": subcategory_key,
                        "category_path": f"{category} > {subcategory} > {brand}",
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    })
                    key += 1
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} product category records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
