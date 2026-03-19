"""
Sales helper for customer and transaction-related generation.

Manages: dim_customers, fact_sales, bridge_order_items, 
         fact_customer_interactions, fact_loyalty_points
"""

from datetime import date
from typing import Dict, List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_accounts import DimAccountsGenerator
from ..entities.dim_customers import DimCustomersGenerator
from ..entities.dim_loyalty_tiers import DimLoyaltyTiersGenerator
from ..entities.fact_sales import FactSalesGenerator
from ..entities.bridge_order_items import BridgeOrderItemsGenerator
from ..entities.bridge_account_customers import BridgeAccountCustomersGenerator
from ..entities.fact_interactions import FactCustomerInteractionsGenerator
from ..entities.fact_loyalty import FactLoyaltyPointsGenerator
from ..utils.customer_selector import CustomerSelector


class SalesHelper(BaseHelper):
    """
    Helper for sales-related entities.
    
    Manages:
    - dim_accounts: Account master data
    - dim_customers: Customer master data (SCD Type 2)
    - bridge_account_customers: Account-customer relationships
    - fact_sales: Sales transactions
    - bridge_order_items: Order line items
    - fact_customer_interactions: Customer touchpoints
    - fact_loyalty_points: Loyalty program transactions
    """
    
    name = "sales"
    
    def __init__(self, config, keys_loader):
        """Initialize sales helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.account_gen = DimAccountsGenerator(config)
        self.customer_gen = DimCustomersGenerator(config)
        self.bridge_ac_gen = BridgeAccountCustomersGenerator(config)
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
        
        # Generate accounts (before customers, since customers reference accounts)
        if self._should_generate("accounts"):
            accounts = self._generate_accounts()
            result.add_dimension(accounts)
            self._update_keys("dim_accounts", accounts.surrogate_keys)
        
        # Generate customers
        if self._should_generate("customers"):
            account_keys = self._get_dimension_keys("dim_accounts")
            customers = self._generate_customers(account_keys=account_keys)
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)
            
            # Generate account-customer bridge
            if account_keys:
                bridge_ac = self._generate_account_customer_bridge(
                    customers_data=customers
                )
                if bridge_ac:
                    result.add_fact(bridge_ac)
                    self._update_keys("bridge_account_customers", bridge_ac.surrogate_keys)
        
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
        
        self._backfill_lifetime_value(result)
        
        return result
    
    def _generate_accounts(
        self,
        count: Optional[int] = None
    ) -> GeneratedData:
        """
        Generate accounts.
        
        Args:
            count: Override volume from config
            
        Returns:
            GeneratedData with account records
        """
        num_accounts = count or self._get_volume("accounts")
        start_key = self._get_next_key("dim_accounts")
        
        self.logger.info(f"Generating {num_accounts} accounts")
        
        return self.account_gen.generate(
            count=num_accounts,
            start_key=start_key
        )
    
    def _generate_account_customer_bridge(
        self,
        customers_data: GeneratedData
    ) -> Optional[GeneratedData]:
        """
        Generate bridge records linking customers to their primary accounts.
        
        Uses account_key from the customer records to build the mapping,
        then generates bridge rows with role assignments.
        """
        import pandas as pd
        
        df = customers_data.data
        if df.empty or "account_key" not in df.columns:
            return None
        
        valid = df[df["account_key"].notna()]
        if valid.empty:
            return None
        
        account_customer_map: dict = {}
        for _, row in valid.iterrows():
            acct_key = int(row["account_key"])
            cust_key = int(row["customer_key"])
            account_customer_map.setdefault(acct_key, []).append(cust_key)
        
        # Build account type lookup from generated accounts data
        account_types: dict = {}
        acct_keys_all = self._get_dimension_keys("dim_accounts")
        if acct_keys_all:
            # Retrieve account type from the generated data via keys_loader cache
            # For simplicity, we don't have direct access to the DataFrame here,
            # so roles will use default logic in the bridge generator
            pass
        
        start_key = self._get_next_key("bridge_account_customers")
        
        return self.bridge_ac_gen.generate(
            start_key=start_key,
            account_customer_map=account_customer_map
        )
    
    def _generate_customers(
        self,
        count: Optional[int] = None,
        registration_date: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        account_keys: Optional[List[int]] = None
    ) -> GeneratedData:
        """
        Generate customers.
        
        Args:
            count: Override volume from config
            registration_date: Specific registration date (single date)
            start_date: Start of date range (if using range)
            end_date: End of date range (if using range)
            account_keys: List of valid account keys for primary account assignment
            
        Returns:
            GeneratedData with customer records
        """
        num_customers = count or self._get_volume("customers")
        start_key = self._get_next_key("dim_customers")
        segment_keys = self._get_dimension_keys("dim_customer_segments")

        # Reconstruct tier data by pairing stored keys with static tier definitions (ordered)
        tier_keys = self._get_dimension_keys("dim_loyalty_tiers")
        loyalty_tier_data = [
            {"tier_key": key, "min_points": tier["min_points"], "max_points": tier["max_points"]}
            for key, tier in zip(tier_keys, DimLoyaltyTiersGenerator.TIERS)
        ] if tier_keys else None

        self.logger.info(f"Generating {num_customers} customers")

        return self.customer_gen.generate(
            count=num_customers,
            start_key=start_key,
            segment_keys=segment_keys,
            account_keys=account_keys,
            loyalty_tier_data=loyalty_tier_data,
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
    
    def _backfill_lifetime_value(self, result: DataGenerationResult) -> None:
        """
        Backfill dim_customers.lifetime_value from fact_sales totals.
        
        Aggregates total_amount by customer_key across all fact_sales DataFrames
        in the result. Only updates customers present in the result (new customers
        during incremental; all during initial load).
        
        Excludes Cancelled/Returned orders from the total.
        """
        customers_data = result.get_table_data("dim_customers")
        if customers_data is None or customers_data.data.empty:
            return
        
        import pandas as pd
        
        # Collect all fact_sales DataFrames (frequent shoppers may produce multiple)
        sales_frames = []
        for table_name, gen_data in result.facts.items():
            if table_name == "fact_sales" and not gen_data.data.empty:
                sales_frames.append(gen_data.data)
        
        if not sales_frames:
            return
        
        all_sales = pd.concat(sales_frames, ignore_index=True)
        
        valid_sales = all_sales[
            ~all_sales["order_status"].isin(["Cancelled", "Returned"])
        ]
        
        if valid_sales.empty:
            return
        
        ltv = valid_sales.groupby("customer_key")["total_amount"].sum()
        
        df = customers_data.data
        df["lifetime_value"] = df["customer_key"].map(ltv).fillna(df["lifetime_value"])
        
        self.logger.info(
            f"Backfilled lifetime_value for {ltv.index.isin(df['customer_key']).sum()} customers"
        )
    
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
        
        # Generate new accounts + customers (1:1 mapping)
        new_customer_keys = []
        if incremental.new_customers > 0:
            num_new = incremental.new_customers

            # Generate matching accounts first
            new_accounts = self._generate_accounts(count=num_new)
            result.add_dimension(new_accounts)
            self._update_keys("dim_accounts", new_accounts.surrogate_keys)

            # Generate customers with only the new account keys (1:1)
            customers = self._generate_customers(
                count=num_new,
                start_date=start,
                end_date=end,
                account_keys=new_accounts.surrogate_keys
            )
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)
            new_customer_keys = customers.surrogate_keys

            # Generate bridge rows for new customers
            bridge_ac = self._generate_account_customer_bridge(
                customers_data=customers
            )
            if bridge_ac:
                result.add_fact(bridge_ac)
                self._update_keys("bridge_account_customers", bridge_ac.surrogate_keys)
        
        # Create customer selector
        existing_keys = self._get_dimension_keys("dim_customers")
        # Remove new keys from existing if they were added
        existing_keys = [k for k in existing_keys if k not in new_customer_keys]
        
        # Build exclusion list: explicit + random
        excluded_keys = list(incremental.excluded_customer_keys or [])
        if incremental.exclude_random_customers > 0 and existing_keys:
            # Randomly select N customers to exclude (that aren't already excluded)
            available_for_exclusion = [k for k in existing_keys if k not in excluded_keys]
            num_to_exclude = min(incremental.exclude_random_customers, len(available_for_exclusion))
            if num_to_exclude > 0:
                random_excluded = random.sample(available_for_exclusion, num_to_exclude)
                excluded_keys.extend(random_excluded)
                self.logger.info(f"Randomly excluded {num_to_exclude} customers: {random_excluded}")
        
        selector = CustomerSelector(
            existing_keys=existing_keys,
            new_keys=new_customer_keys,
            existing_ratio=incremental.existing_customer_ratio,
            excluded_keys=excluded_keys if excluded_keys else None
        )
        
        # Get dimension keys
        dimension_keys = self.keys_loader.get_all_dimension_keys()
        
        # Generate orders (distributed across date range)
        if incremental.new_orders > 0:
            all_sales_keys = []
            frequent_orders_count = 0
            
            # Handle frequent shoppers first - they get multiple orders each
            if incremental.frequent_shopper_count > 0 and selector.existing_keys:
                # Select N existing customers to be frequent shoppers
                available_frequent = selector.existing_keys.copy()
                num_frequent = min(incremental.frequent_shopper_count, len(available_frequent))
                
                if num_frequent > 0:
                    frequent_customers = random.sample(available_frequent, num_frequent)
                    self.logger.info(f"Selected {num_frequent} frequent shoppers: {frequent_customers}")
                    
                    # Generate multiple orders for each frequent shopper
                    for customer_key in frequent_customers:
                        num_orders = random.randint(
                            incremental.frequent_shopper_min_orders,
                            incremental.frequent_shopper_max_orders
                        )
                        
                        # Generate orders for this frequent shopper
                        frequent_sales = self._generate_sales(
                            dimension_keys=dimension_keys,
                            count=num_orders,
                            start_date=start,
                            end_date=end,
                            customer_selector=None  # Will use fixed customer
                        )
                        
                        # Override customer_key for all these orders
                        frequent_sales.data['customer_key'] = customer_key
                        
                        result.add_fact(frequent_sales)
                        all_sales_keys.extend(frequent_sales.surrogate_keys)
                        frequent_orders_count += num_orders
                        self.logger.debug(f"Frequent shopper {customer_key}: {num_orders} orders")
                    
                    self.logger.info(f"Generated {frequent_orders_count} orders for {num_frequent} frequent shoppers")
            
            # Generate remaining orders using normal distribution
            remaining_orders = max(0, incremental.new_orders - frequent_orders_count)
            if remaining_orders > 0:
                sales = self._generate_sales(
                    dimension_keys=dimension_keys,
                    count=remaining_orders,
                    start_date=start,
                    end_date=end,
                    customer_selector=selector
                )
                result.add_fact(sales)
                all_sales_keys.extend(sales.surrogate_keys)
            
            self._update_keys("fact_sales", all_sales_keys)
            
            # Generate order items for all orders
            product_keys = dimension_keys.get("dim_products", [])
            order_items = self._generate_order_items(
                sale_keys=all_sales_keys,
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
        
        self._backfill_lifetime_value(result)
        
        return result
