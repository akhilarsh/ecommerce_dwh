"""
Sales helper for customer and transaction-related generation.

Manages: dim_customers, fact_sales, bridge_order_items, 
         fact_customer_interactions, fact_loyalty_points
"""

from datetime import date
from typing import Dict, List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_customers import DimCustomersGenerator
from ..entities.fact_sales import FactSalesGenerator
from ..entities.bridge_order_items import BridgeOrderItemsGenerator
from ..entities.fact_interactions import FactCustomerInteractionsGenerator
from ..entities.fact_loyalty import FactLoyaltyPointsGenerator
from ..utils.customer_selector import CustomerSelector


class SalesHelper(BaseHelper):
    """
    Helper for sales-related entities.
    
    Manages:
    - dim_customers: Customer master data (SCD Type 2)
    - fact_sales: Sales transactions
    - bridge_order_items: Order line items
    - fact_customer_interactions: Customer touchpoints
    - fact_loyalty_points: Loyalty program transactions
    """
    
    name = "sales"
    
    def __init__(self, config, keys_loader):
        """Initialize sales helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.customer_gen = DimCustomersGenerator(config)
        self.sales_gen = FactSalesGenerator(config)
        self.order_items_gen = BridgeOrderItemsGenerator(config)
        self.interactions_gen = FactCustomerInteractionsGenerator(config)
        self.loyalty_gen = FactLoyaltyPointsGenerator(config)
    
    def generate(self) -> DataGenerationResult:
        """
        Generate all sales-domain entities based on config.volumes.
        
        Returns:
            DataGenerationResult with sales data
        """
        result = DataGenerationResult()
        
        # Generate customers
        if self._should_generate("customers"):
            customers = self._generate_customers()
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)
        
        # Get dimension keys for fact generation
        dimension_keys = self.keys_loader.get_all_dimension_keys()
        
        # Generate sales
        if self._should_generate("sales"):
            sales = self._generate_sales(dimension_keys)
            result.add_fact(sales)
            self._update_keys("fact_sales", sales.surrogate_keys)
            
            # Generate order items for sales
            product_keys = dimension_keys.get("dim_products", [])
            order_items = self._generate_order_items(
                sale_keys=sales.surrogate_keys,
                product_keys=product_keys
            )
            result.add_fact(order_items)
            self._update_keys("bridge_order_items", order_items.surrogate_keys)
        
        # Generate interactions
        if self._should_generate("customer_interactions"):
            sale_keys = self._get_dimension_keys("fact_sales")
            interactions = self._generate_interactions(
                dimension_keys=dimension_keys,
                sale_keys=sale_keys
            )
            result.add_fact(interactions)
            self._update_keys("fact_customer_interactions", interactions.surrogate_keys)
        
        # Generate loyalty transactions
        if self._should_generate("loyalty_transactions"):
            sale_keys = self._get_dimension_keys("fact_sales")
            loyalty_customer_keys = self._get_loyalty_members()
            loyalty = self._generate_loyalty(
                dimension_keys=dimension_keys,
                sale_keys=sale_keys,
                loyalty_customer_keys=loyalty_customer_keys
            )
            result.add_fact(loyalty)
            self._update_keys("fact_loyalty_points", loyalty.surrogate_keys)
        
        return result
    
    def _generate_customers(
        self,
        count: Optional[int] = None,
        registration_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> GeneratedData:
        """
        Generate customers.
        
        Args:
            count: Override volume from config
            registration_date: Specific registration date (single date)
            start_date: Start of date range (if using range)
            end_date: End of date range (if using range)
            
        Returns:
            GeneratedData with customer records
        """
        num_customers = count or self._get_volume("customers")
        start_key = self._get_next_key("dim_customers")
        segment_keys = self._get_dimension_keys("dim_customer_segments")
        
        self.logger.info(f"Generating {num_customers} customers")
        
        return self.customer_gen.generate(
            count=num_customers,
            start_key=start_key,
            segment_keys=segment_keys,
            registration_date=registration_date,
            start_date=start_date,
            end_date=end_date
        )
    
    def _generate_sales(
        self,
        dimension_keys: Dict[str, List[int]],
        count: Optional[int] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_selector: Optional[CustomerSelector] = None
    ) -> GeneratedData:
        """
        Generate sales.
        
        Args:
            dimension_keys: Dictionary of dimension keys
            count: Override volume from config
            target_date: Specific date for sales (single date)
            start_date: Start of date range (if using range)
            end_date: End of date range (if using range)
            customer_selector: Customer selector for ratio-based selection
            
        Returns:
            GeneratedData with sales records
        """
        num_sales = count or self._get_volume("sales")
        start_key = self._get_next_key("fact_sales")
        
        self.logger.info(f"Generating {num_sales} sales")
        
        return self.sales_gen.generate(
            count=num_sales,
            start_key=start_key,
            dimension_keys=dimension_keys,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
            customer_selector=customer_selector
        )
    
    def _generate_order_items(
        self,
        sale_keys: List[int],
        product_keys: List[int]
    ) -> GeneratedData:
        """
        Generate order items for sales.
        
        Args:
            sale_keys: Sale keys to create items for
            product_keys: Available product keys
            
        Returns:
            GeneratedData with order item records
        """
        start_key = self._get_next_key("bridge_order_items")
        
        self.logger.info(f"Generating order items for {len(sale_keys)} sales")
        
        return self.order_items_gen.generate(
            start_key=start_key,
            sale_keys=sale_keys,
            product_keys=product_keys,
            min_items_per_order=self.config.incremental.min_items_per_order,
            max_items_per_order=self.config.incremental.max_items_per_order
        )
    
    def _generate_interactions(
        self,
        dimension_keys: Dict[str, List[int]],
        sale_keys: Optional[List[int]] = None,
        count: Optional[int] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_selector: Optional[CustomerSelector] = None
    ) -> GeneratedData:
        """
        Generate customer interactions.
        
        Args:
            dimension_keys: Dictionary of dimension keys
            sale_keys: Sale keys for purchase-linked interactions
            count: Override volume from config
            target_date: Specific date for interactions (single date)
            start_date: Start of date range (if using range)
            end_date: End of date range (if using range)
            customer_selector: Customer selector for ratio-based selection
            
        Returns:
            GeneratedData with interaction records
        """
        num_interactions = count or self._get_volume("customer_interactions")
        start_key = self._get_next_key("fact_customer_interactions")
        
        self.logger.info(f"Generating {num_interactions} interactions")
        
        return self.interactions_gen.generate(
            count=num_interactions,
            start_key=start_key,
            dimension_keys=dimension_keys,
            sale_keys=sale_keys,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
            customer_selector=customer_selector
        )
    
    def _generate_loyalty(
        self,
        dimension_keys: Dict[str, List[int]],
        sale_keys: Optional[List[int]] = None,
        loyalty_customer_keys: Optional[List[int]] = None,
        count: Optional[int] = None,
        target_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_selector: Optional[CustomerSelector] = None
    ) -> GeneratedData:
        """
        Generate loyalty transactions.
        
        Args:
            dimension_keys: Dictionary of dimension keys
            sale_keys: Sale keys for earned points
            loyalty_customer_keys: Customer keys who are loyalty members
            count: Override volume from config
            target_date: Specific date for transactions (single date)
            start_date: Start of date range (if using range)
            end_date: End of date range (if using range)
            customer_selector: Customer selector for ratio-based selection
            
        Returns:
            GeneratedData with loyalty transaction records
        """
        num_loyalty = count or self._get_volume("loyalty_transactions")
        start_key = self._get_next_key("fact_loyalty_points")
        
        self.logger.info(f"Generating {num_loyalty} loyalty transactions")
        
        return self.loyalty_gen.generate(
            count=num_loyalty,
            start_key=start_key,
            dimension_keys=dimension_keys,
            sale_keys=sale_keys,
            loyalty_customer_keys=loyalty_customer_keys,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
            customer_selector=customer_selector
        )
    
    def _get_loyalty_members(self) -> List[int]:
        """Get customer keys for loyalty program members."""
        # In a real implementation, this would query the customers table
        # For now, return all customers (60% are loyalty members by default)
        return self._get_dimension_keys("dim_customers")
    
    def generate_incremental(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DataGenerationResult:
        """
        Generate incremental data using config.incremental settings.
        
        Data is distributed across the date range. Each record gets a random
        date within the range.
        
        Args:
            start_date: Start of date range (defaults to config.incremental.start_date)
            end_date: End of date range (defaults to config.incremental.end_date)
            
        Returns:
            DataGenerationResult with incremental operations
        """
        import random
        from datetime import timedelta
        
        result = DataGenerationResult()
        incremental = self.config.incremental
        
        # Use provided dates or fall back to config
        start = start_date or incremental.start_date or date.today()
        end = end_date or incremental.end_date or date.today()
        
        # Ensure start <= end
        if start > end:
            start, end = end, start
        
        def random_date_in_range() -> date:
            """Get a random date within the range."""
            delta = (end - start).days
            if delta == 0:
                return start
            return start + timedelta(days=random.randint(0, delta))
        
        self.logger.info(f"Generating incremental data for {start} to {end}")
        
        # Generate new customers (distributed across date range)
        new_customer_keys = []
        if incremental.new_customers > 0:
            customers = self._generate_customers(
                count=incremental.new_customers,
                start_date=start,
                end_date=end
            )
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)
            new_customer_keys = customers.surrogate_keys
        
        # Create customer selector
        existing_keys = self._get_dimension_keys("dim_customers")
        # Remove new keys from existing if they were added
        existing_keys = [k for k in existing_keys if k not in new_customer_keys]
        
        selector = CustomerSelector(
            existing_keys=existing_keys,
            new_keys=new_customer_keys,
            existing_ratio=incremental.existing_customer_ratio
        )
        
        # Get dimension keys
        dimension_keys = self.keys_loader.get_all_dimension_keys()
        
        # Generate orders (distributed across date range)
        if incremental.new_orders > 0:
            sales = self._generate_sales(
                dimension_keys=dimension_keys,
                count=incremental.new_orders,
                start_date=start,
                end_date=end,
                customer_selector=selector
            )
            result.add_fact(sales)
            self._update_keys("fact_sales", sales.surrogate_keys)
            
            # Generate order items
            product_keys = dimension_keys.get("dim_products", [])
            order_items = self._generate_order_items(
                sale_keys=sales.surrogate_keys,
                product_keys=product_keys
            )
            result.add_fact(order_items)
            self._update_keys("bridge_order_items", order_items.surrogate_keys)
        
        # Generate interactions (distributed across date range)
        if incremental.new_interactions > 0:
            sale_keys = self._get_dimension_keys("fact_sales")
            interactions = self._generate_interactions(
                dimension_keys=dimension_keys,
                sale_keys=sale_keys,
                count=incremental.new_interactions,
                start_date=start,
                end_date=end,
                customer_selector=selector
            )
            result.add_fact(interactions)
            self._update_keys("fact_customer_interactions", interactions.surrogate_keys)
        
        # Generate loyalty (distributed across date range)
        if incremental.new_loyalty_transactions > 0:
            sale_keys = self._get_dimension_keys("fact_sales")
            loyalty = self._generate_loyalty(
                dimension_keys=dimension_keys,
                sale_keys=sale_keys,
                count=incremental.new_loyalty_transactions,
                start_date=start,
                end_date=end,
                customer_selector=selector
            )
            result.add_fact(loyalty)
            self._update_keys("fact_loyalty_points", loyalty.surrogate_keys)
        
        return result
