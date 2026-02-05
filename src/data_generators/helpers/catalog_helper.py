"""
Catalog helper for product-related dimension generation.

Manages: dim_product_categories, dim_products, dim_promotions, bridge_product_promotions
"""

from datetime import date
from typing import List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_product_categories import DimProductCategoriesGenerator
from ..entities.dim_products import DimProductsGenerator
from ..entities.dim_promotions import DimPromotionsGenerator
from ..entities.bridge_product_promotions import BridgeProductPromotionsGenerator


class CatalogHelper(BaseHelper):
    """
    Helper for product catalog dimensions.
    
    Manages:
    - dim_product_categories: Product hierarchy
    - dim_products: Product catalog (SCD Type 2)
    - dim_promotions: Marketing campaigns
    - bridge_product_promotions: Product-promotion associations
    """
    
    name = "catalog"
    
    def __init__(self, config, keys_loader):
        """Initialize catalog helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.category_gen = DimProductCategoriesGenerator(config)
        self.product_gen = DimProductsGenerator(config)
        self.promotion_gen = DimPromotionsGenerator(config)
        self.product_promo_gen = BridgeProductPromotionsGenerator(config)
    
    def generate(self) -> DataGenerationResult:
        """
        Generate all catalog dimensions based on config.volumes.
        
        Returns:
            DataGenerationResult with catalog dimensions
        """
        result = DataGenerationResult()
        
        # Generate categories first (products depend on them)
        if self._should_generate("product_categories"):
            categories = self._generate_categories()
            result.add_dimension(categories)
            self._update_keys("dim_product_categories", categories.surrogate_keys)
        
        # Generate products
        if self._should_generate("products"):
            category_keys = self._get_dimension_keys("dim_product_categories")
            products = self._generate_products(category_keys)
            result.add_dimension(products)
            self._update_keys("dim_products", products.surrogate_keys)
        
        # Generate promotions
        if self._should_generate("promotions"):
            promotions = self._generate_promotions()
            result.add_dimension(promotions)
            self._update_keys("dim_promotions", promotions.surrogate_keys)
            
            # Generate product-promotion links
            product_keys = self._get_dimension_keys("dim_products")
            promo_links = self._generate_product_promotions(
                promotion_keys=promotions.surrogate_keys,
                product_keys=product_keys
            )
            result.add_fact(promo_links)
            self._update_keys("bridge_product_promotions", promo_links.surrogate_keys)
        
        return result
    
    def _generate_categories(self) -> GeneratedData:
        """Generate product category hierarchy."""
        start_key = self._get_next_key("dim_product_categories")
        
        self.logger.info("Generating product categories")
        
        return self.category_gen.generate(start_key=start_key)
    
    def _generate_products(
        self,
        category_keys: List[int],
        count: Optional[int] = None
    ) -> GeneratedData:
        """
        Generate products.
        
        Args:
            category_keys: Valid category keys for assignment
            count: Override volume from config
            
        Returns:
            GeneratedData with product records
        """
        num_products = count or self._get_volume("products")
        start_key = self._get_next_key("dim_products")
        
        self.logger.info(f"Generating {num_products} products")
        
        return self.product_gen.generate(
            count=num_products,
            start_key=start_key,
            category_keys=category_keys
        )
    
    def _generate_promotions(
        self,
        count: Optional[int] = None
    ) -> GeneratedData:
        """
        Generate promotions.
        
        Args:
            count: Override volume from config
            
        Returns:
            GeneratedData with promotion records
        """
        num_promotions = count or self._get_volume("promotions")
        start_key = self._get_next_key("dim_promotions")
        
        self.logger.info(f"Generating {num_promotions} promotions")
        
        return self.promotion_gen.generate(
            count=num_promotions,
            start_key=start_key
        )
    
    def _generate_product_promotions(
        self,
        promotion_keys: List[int],
        product_keys: List[int]
    ) -> GeneratedData:
        """
        Generate product-promotion associations.
        
        Args:
            promotion_keys: Promotion keys to link
            product_keys: Available product keys
            
        Returns:
            GeneratedData with product-promotion links
        """
        start_key = self._get_next_key("bridge_product_promotions")
        
        self.logger.info(f"Generating product-promotion links")
        
        return self.product_promo_gen.generate(
            start_key=start_key,
            promotion_keys=promotion_keys,
            product_keys=product_keys
        )
    
    def add_promotion_campaign(
        self,
        campaign_name: str,
        start_date: date,
        end_date: date,
        discount_min: float = 0.10,
        discount_max: float = 0.30,
        products_count: int = 20
    ) -> DataGenerationResult:
        """
        Add a new promotion campaign with product associations.
        
        Args:
            campaign_name: Name of the campaign
            start_date: Campaign start date
            end_date: Campaign end date
            discount_min: Minimum discount percentage
            discount_max: Maximum discount percentage
            products_count: Number of products to include
            
        Returns:
            DataGenerationResult with promotion and links
        """
        result = DataGenerationResult()
        
        # Generate single promotion
        from datetime import datetime
        promo_key = self._get_next_key("dim_promotions")
        
        promotion = self.promotion_gen.generate(
            count=1,
            start_key=promo_key,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.min.time())
        )
        
        # Override generated name with provided name
        if promotion.row_count > 0:
            promotion.data.loc[0, "promotion_name"] = campaign_name
        
        result.add_dimension(promotion)
        self._update_keys("dim_promotions", promotion.surrogate_keys)
        
        # Generate product links
        product_keys = self._get_dimension_keys("dim_products")
        if product_keys:
            links = self._generate_product_promotions(
                promotion_keys=[promo_key],
                product_keys=product_keys[:products_count]
            )
            result.add_fact(links)
            self._update_keys("bridge_product_promotions", links.surrogate_keys)
        
        return result
