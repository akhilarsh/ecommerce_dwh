"""
Sales helper for customer and transaction-related generation.

Manages: dim_customers, dim_customer_address, dim_customer_loyalty,
         fact_sales, bridge_order_items, bridge_account_customers,
         fact_customer_interactions, fact_loyalty_points
"""

from datetime import date
from typing import Dict, List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_accounts import DimAccountsGenerator
from ..entities.dim_customers import DimCustomersGenerator
from ..entities.dim_customer_address import DimCustomerAddressGenerator
from ..entities.dim_customer_loyalty import DimCustomerLoyaltyGenerator
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
    - dim_customers: Customer profile (SCD Type 2)
    - dim_customer_address: Customer addresses (SCD Type 2)
    - dim_customer_loyalty: Loyalty program metrics (SCD Type 2)
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
        self.customer_address_gen = DimCustomerAddressGenerator(config)
        self.customer_loyalty_gen = DimCustomerLoyaltyGenerator(config)
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

        # Generate accounts (before customers, since loyalty references accounts)
        if self._should_generate("accounts"):
            accounts = self._generate_accounts()
            result.add_dimension(accounts)
            self._update_keys("dim_accounts", accounts.surrogate_keys)

        # Generate customers (profile only)
        if self._should_generate("customers"):
            customers = self._generate_customers()
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)

            customer_keys = customers.surrogate_keys
            account_keys = self._get_dimension_keys("dim_accounts")

            # Generate customer addresses (one per customer)
            addresses = self._generate_customer_addresses(
                customer_keys=customer_keys
            )
            result.add_dimension(addresses)
            self._update_keys("dim_customer_address", addresses.surrogate_keys)

            # Generate customer loyalty (one per customer)
            loyalty_records = self._generate_customer_loyalty(
                customer_keys=customer_keys,
                account_keys=account_keys
            )
            result.add_dimension(loyalty_records)
            self._update_keys("dim_customer_loyalty", loyalty_records.surrogate_keys)

            # Generate account-customer bridge using loyalty data (which has account_key)
            if account_keys:
                bridge_ac = self._generate_account_customer_bridge(
                    customer_keys=customer_keys,
                    loyalty_data=loyalty_records
                )
                if bridge_ac:
                    result.add_fact(bridge_ac)
                    self._update_keys("bridge_account_customers", bridge_ac.surrogate_keys)

        # Get dimension keys for fact generation
        dimension_keys = self.keys_loader.get_all_dimension_keys()

        # Pick N customers to receive zero orders (initial-load "dormant" cohort).
        no_order_count = self._get_volume("customers_without_orders")
        no_order_customer_keys: List[int] = []
        sales_selector: Optional[CustomerSelector] = None
        if no_order_count > 0:
            import random
            all_customer_keys = dimension_keys.get("dim_customers", [])
            if no_order_count >= len(all_customer_keys):
                self.logger.warning(
                    f"customers_without_orders ({no_order_count}) >= "
                    f"customers ({len(all_customer_keys)}); skipping exclusion"
                )
            else:
                no_order_customer_keys = random.sample(all_customer_keys, no_order_count)
                self.logger.info(
                    f"Excluding {no_order_count} customers from initial sales: "
                    f"{no_order_customer_keys[:10]}{'...' if no_order_count > 10 else ''}"
                )
                sales_selector = CustomerSelector(
                    existing_keys=all_customer_keys,
                    excluded_keys=no_order_customer_keys,
                )

        # Generate sales
        if self._should_generate("sales"):
            sales = self._generate_sales(
                dimension_keys, customer_selector=sales_selector
            )
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
        """Generate accounts."""
        num_accounts = count or self._get_volume("accounts")
        start_key = self._get_next_key("dim_accounts")
        self.logger.info(f"Generating {num_accounts} accounts")
        return self.account_gen.generate(count=num_accounts, start_key=start_key)

    def _generate_customers(
        self,
        count: Optional[int] = None,
        effective_date: Optional[date] = None
    ) -> GeneratedData:
        """Generate customer profiles."""
        num_customers = count or self._get_volume("customers")
        start_key = self._get_next_key("dim_customers")
        segment_keys = self._get_dimension_keys("dim_customer_segments")
        self.logger.info(f"Generating {num_customers} customers")
        return self.customer_gen.generate(
            count=num_customers,
            start_key=start_key,
            segment_keys=segment_keys,
            effective_date=effective_date
        )

    def _generate_customer_addresses(
        self,
        customer_keys: List[int],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        effective_date: Optional[date] = None
    ) -> GeneratedData:
        """Generate one address per customer."""
        start_key = self._get_next_key("dim_customer_address")
        self.logger.info(f"Generating {len(customer_keys)} customer addresses")
        return self.customer_address_gen.generate(
            customer_keys=customer_keys,
            start_key=start_key,
            start_date=start_date,
            end_date=end_date,
            effective_date=effective_date
        )

    def _generate_customer_loyalty(
        self,
        customer_keys: List[int],
        account_keys: Optional[List[int]] = None,
        effective_date: Optional[date] = None
    ) -> GeneratedData:
        """Generate one loyalty record per customer."""
        start_key = self._get_next_key("dim_customer_loyalty")

        tier_keys = self._get_dimension_keys("dim_loyalty_tiers")
        loyalty_tier_data = [
            {"tier_key": key, "min_points": tier["min_points"], "max_points": tier["max_points"]}
            for key, tier in zip(tier_keys, DimLoyaltyTiersGenerator.TIERS)
        ] if tier_keys else None

        self.logger.info(f"Generating {len(customer_keys)} customer loyalty records")
        return self.customer_loyalty_gen.generate(
            customer_keys=customer_keys,
            start_key=start_key,
            account_keys=account_keys,
            loyalty_tier_data=loyalty_tier_data,
            effective_date=effective_date
        )

    def _generate_account_customer_bridge(
        self,
        customer_keys: List[int],
        loyalty_data: GeneratedData
    ) -> Optional[GeneratedData]:
        """
        Generate bridge records linking customers to their primary accounts.

        Uses account_key from loyalty records to build the mapping.
        """
        df = loyalty_data.data
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

        start_key = self._get_next_key("bridge_account_customers")
        return self.bridge_ac_gen.generate(
            start_key=start_key,
            account_customer_map=account_customer_map
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
        """Generate sales."""
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
        """Generate order items for sales."""
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
        """Generate customer interactions."""
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
        """Generate loyalty transactions."""
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
        return self._get_dimension_keys("dim_customers")

    def _backfill_lifetime_value(self, result: DataGenerationResult) -> None:
        """
        Backfill dim_customer_loyalty.lifetime_value from fact_sales totals.

        Aggregates total_amount by customer_key across all fact_sales DataFrames.
        Excludes Cancelled/Returned orders from the total.
        """
        loyalty_data = result.get_table_data("dim_customer_loyalty")
        if loyalty_data is None or loyalty_data.data.empty:
            return

        import pandas as pd

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

        df = loyalty_data.data
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

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            DataGenerationResult with incremental operations
        """
        import random
        from datetime import timedelta

        result = DataGenerationResult()
        incremental = self.config.incremental

        start = start_date or incremental.start_date or date.today()
        end = end_date or incremental.end_date or date.today()

        if start > end:
            start, end = end, start

        self.logger.info(f"Generating incremental data for {start} to {end}")

        new_customer_keys = []
        if incremental.new_customers > 0:
            num_new = incremental.new_customers
            account_keys = list(self._get_dimension_keys("dim_accounts"))

            new_account_keys = []
            new_accounts_count = incremental.new_accounts or 0
            if new_accounts_count > 0:
                new_accounts = self._generate_accounts(count=new_accounts_count)
                result.add_dimension(new_accounts)
                self._update_keys("dim_accounts", new_accounts.surrogate_keys)
                new_account_keys = new_accounts.surrogate_keys

            pool = account_keys + new_account_keys
            if not pool:
                self.logger.warning("No account keys available; loyalty records will have account_key=NULL")

            customers = self._generate_customers(count=num_new)
            result.add_dimension(customers)
            self._update_keys("dim_customers", customers.surrogate_keys)
            new_customer_keys = customers.surrogate_keys

            # Generate addresses for new customers
            addresses = self._generate_customer_addresses(
                customer_keys=new_customer_keys,
                start_date=start,
                end_date=end
            )
            result.add_dimension(addresses)
            self._update_keys("dim_customer_address", addresses.surrogate_keys)

            # Generate loyalty for new customers
            loyalty_records = self._generate_customer_loyalty(
                customer_keys=new_customer_keys,
                account_keys=pool if pool else None
            )
            result.add_dimension(loyalty_records)
            self._update_keys("dim_customer_loyalty", loyalty_records.surrogate_keys)

            bridge_ac = self._generate_account_customer_bridge(
                customer_keys=new_customer_keys,
                loyalty_data=loyalty_records
            )
            if bridge_ac:
                result.add_fact(bridge_ac)
                self._update_keys("bridge_account_customers", bridge_ac.surrogate_keys)

        # Create customer selector
        existing_keys = self._get_dimension_keys("dim_customers")
        existing_keys = [k for k in existing_keys if k not in new_customer_keys]

        excluded_keys = list(incremental.excluded_customer_keys or [])
        if incremental.exclude_random_customers > 0 and existing_keys:
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

        dimension_keys = self.keys_loader.get_all_dimension_keys()

        if incremental.new_orders > 0:
            all_sales_keys = []
            frequent_orders_count = 0

            if incremental.frequent_shopper_count > 0 and selector.existing_keys:
                available_frequent = selector.existing_keys.copy()
                num_frequent = min(incremental.frequent_shopper_count, len(available_frequent))

                if num_frequent > 0:
                    frequent_customers = random.sample(available_frequent, num_frequent)
                    self.logger.info(f"Selected {num_frequent} frequent shoppers: {frequent_customers}")

                    for customer_key in frequent_customers:
                        num_orders = random.randint(
                            incremental.frequent_shopper_min_orders,
                            incremental.frequent_shopper_max_orders
                        )
                        frequent_sales = self._generate_sales(
                            dimension_keys=dimension_keys,
                            count=num_orders,
                            start_date=start,
                            end_date=end
                        )
                        frequent_sales.data['customer_key'] = customer_key
                        result.add_fact(frequent_sales)
                        all_sales_keys.extend(frequent_sales.surrogate_keys)
                        frequent_orders_count += num_orders
                        self.logger.debug(f"Frequent shopper {customer_key}: {num_orders} orders")

                    self.logger.info(
                        f"Generated {frequent_orders_count} orders for {num_frequent} frequent shoppers"
                    )

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

            product_keys = dimension_keys.get("dim_products", [])
            order_items = self._generate_order_items(
                sale_keys=all_sales_keys,
                product_keys=product_keys
            )
            result.add_fact(order_items)
            self._update_keys("bridge_order_items", order_items.surrogate_keys)

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
