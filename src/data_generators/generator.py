"""
Main DataGenerator class for E-Commerce Data Warehouse.

Single entry point for all data generation. Delegates to domain helpers
and coordinates generation order for referential integrity.
"""

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from .config import DataGenConfig, load_config
from .helpers.base_helper import DataGenerationResult, GeneratedData
from .helpers.calendar_helper import CalendarHelper
from .helpers.catalog_helper import CatalogHelper
from .helpers.store_helper import StoreHelper
from .helpers.sales_helper import SalesHelper
from .helpers.inventory_helper import InventoryHelper
from .utils.keys_loader import ExistingKeysLoader
from ..utils.logger import get_logger


class DataGenerator:
    """
    Main entry point for all data generation.
    
    Config-driven: generates entities with non-zero config values.
    Coordinates domain helpers to ensure proper referential integrity.
    
    Usage:
        # Basic usage with defaults
        gen = DataGenerator()
        result = gen.generate_initial()
        
        # With custom config
        gen = DataGenerator(config_path="custom_config.yaml")
        result = gen.generate_initial()
        
        # Incremental generation
        gen.load_keys_from_cache("outputs/keys_cache.json")
        result = gen.generate_incremental(date.today())
    """
    
    def __init__(self, config_path: Optional[str] = None, config: Optional[DataGenConfig] = None):
        """
        Initialize the data generator.
        
        Args:
            config_path: Path to YAML config file (optional)
            config: DataGenConfig instance (optional, overrides config_path)
        """
        self.logger = get_logger("generator")
        
        # Load configuration
        if config is not None:
            self.config = config
        else:
            self.config = load_config(config_path)
        
        # Initialize keys loader
        self.keys_loader = ExistingKeysLoader()
        self.keys_loader.initialize_empty()
        
        # Initialize helpers
        self.calendar = CalendarHelper(self.config, self.keys_loader)
        self.catalog = CatalogHelper(self.config, self.keys_loader)
        self.store = StoreHelper(self.config, self.keys_loader)
        self.sales = SalesHelper(self.config, self.keys_loader)
        self.inventory = InventoryHelper(self.config, self.keys_loader)
        
        self.logger.info("DataGenerator initialized")
    
    def generate_initial(self, validate: bool = True) -> DataGenerationResult:
        """
        Generate initial bulk load based on config.volumes.
        
        Skips any entity with 0 or missing volume.
        
        Args:
            validate: Whether to validate referential integrity
            
        Returns:
            DataGenerationResult with all generated data
        """
        self.logger.info("Starting initial data generation")
        result = DataGenerationResult()
        
        # Order matters for referential integrity:
        # 1. Static dimensions (no FK dependencies)
        self.logger.info("Phase 1: Generating static dimensions")
        result.merge(self._generate_static_dimensions())
        
        # 2. Calendar dimensions
        self.logger.info("Phase 2: Generating calendar dimensions")
        result.merge(self.calendar.generate())
        
        # 3. Catalog dimensions
        self.logger.info("Phase 3: Generating catalog dimensions")
        result.merge(self.catalog.generate())
        
        # 4. Store dimensions
        self.logger.info("Phase 4: Generating store dimensions")
        result.merge(self.store.generate())
        
        # 5. Sales domain (customers, sales, interactions, loyalty)
        self.logger.info("Phase 5: Generating sales domain")
        result.merge(self.sales.generate())
        
        # 6. Inventory snapshots
        self.logger.info("Phase 6: Generating inventory snapshots")
        result.merge(self.inventory.generate())
        
        # Validate if requested
        if validate and self.config.settings.validate_integrity:
            self.logger.info("Phase 7: Validating referential integrity")
            self._validate(result)
        
        self.logger.info(f"Initial generation complete: {result.total_records} total records")
        return result
    
    def _generate_static_dimensions(self) -> DataGenerationResult:
        """Generate static dimensions that have no FK dependencies."""
        from .entities.dim_channels import DimChannelsGenerator
        from .entities.dim_payment_methods import DimPaymentMethodsGenerator
        from .entities.dim_shipping_methods import DimShippingMethodsGenerator
        from .entities.dim_customer_segments import DimCustomerSegmentsGenerator
        from .entities.dim_loyalty_tiers import DimLoyaltyTiersGenerator
        
        result = DataGenerationResult()
        
        # Channels
        channel_gen = DimChannelsGenerator(self.config)
        channels = channel_gen.generate(start_key=self.keys_loader.get_next_key("dim_channels"))
        result.add_dimension(channels)
        self.keys_loader.update_after_generation("dim_channels", channels.surrogate_keys)
        
        # Payment methods
        payment_gen = DimPaymentMethodsGenerator(self.config)
        payments = payment_gen.generate(start_key=self.keys_loader.get_next_key("dim_payment_methods"))
        result.add_dimension(payments)
        self.keys_loader.update_after_generation("dim_payment_methods", payments.surrogate_keys)
        
        # Shipping methods
        shipping_gen = DimShippingMethodsGenerator(self.config)
        shipping = shipping_gen.generate(start_key=self.keys_loader.get_next_key("dim_shipping_methods"))
        result.add_dimension(shipping)
        self.keys_loader.update_after_generation("dim_shipping_methods", shipping.surrogate_keys)
        
        # Customer segments
        segment_gen = DimCustomerSegmentsGenerator(self.config)
        segments = segment_gen.generate(start_key=self.keys_loader.get_next_key("dim_customer_segments"))
        result.add_dimension(segments)
        self.keys_loader.update_after_generation("dim_customer_segments", segments.surrogate_keys)

        # Loyalty tiers
        loyalty_tier_gen = DimLoyaltyTiersGenerator(self.config)
        loyalty_tiers = loyalty_tier_gen.generate(start_key=self.keys_loader.get_next_key("dim_loyalty_tiers"))
        result.add_dimension(loyalty_tiers)
        self.keys_loader.update_after_generation("dim_loyalty_tiers", loyalty_tiers.surrogate_keys)

        return result
    
    def generate_incremental(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DataGenerationResult:
        """
        Generate incremental data based on config.incremental.
        
        Data is distributed across the date range.
        Adds missing dates to dim_dates for the incremental range.
        
        Args:
            start_date: Start of date range (defaults to config.incremental.start_date)
            end_date: End of date range (defaults to config.incremental.end_date)
            
        Returns:
            DataGenerationResult with incremental operations
        """
        from .utils.date_keys import date_to_key
        
        start = start_date or self.config.incremental.start_date
        end = end_date or self.config.incremental.end_date
        self.logger.info(f"Generating incremental data for: {start} to {end}")
        
        result = DataGenerationResult()
        
        # Add missing dates for incremental range (fixes FK violations)
        existing_date_keys = set(
            self.keys_loader.get_valid_fk_keys("dim_dates") or []
        )
        missing_dates = []
        d = start
        while d <= end:
            if date_to_key(d) not in existing_date_keys:
                missing_dates.append(d)
            d += timedelta(days=1)
        
        if missing_dates:
            min_d, max_d = min(missing_dates), max(missing_dates)
            missing_keys = {date_to_key(d) for d in missing_dates}
            self.logger.info(
                f"Adding {len(missing_dates)} missing dates to dim_dates "
                f"({min_d} to {max_d})"
            )
            dates_data = self.calendar.generate_date_for_range(min_d, max_d)
            if len(missing_keys) < len(dates_data.surrogate_keys):
                from .helpers.base_helper import GeneratedData
                df = dates_data.data
                dates_data = GeneratedData(
                    table_name=dates_data.table_name,
                    data=df[df["date_key"].isin(missing_keys)].copy(),
                    surrogate_keys=[k for k in dates_data.surrogate_keys if k in missing_keys],
                )
            result.add_dimension(dates_data)
            self.keys_loader.update_after_generation(
                "dim_dates", dates_data.surrogate_keys
            )
        
        sales_result = self.sales.generate_incremental(
            start_date=start, end_date=end
        )
        result.merge(sales_result)
        return result
    
    def generate_inventory_snapshot(self, target_date: date) -> GeneratedData:
        """
        Generate inventory snapshot for a date.
        
        Args:
            target_date: Date for the snapshot
            
        Returns:
            GeneratedData with inventory snapshot
        """
        self.logger.info(f"Generating inventory snapshot for: {target_date}")
        return self.inventory.generate_snapshot(target_date)
    
    def generate_store_opening(
        self,
        store_name: str,
        store_type: str = "Mall",
        region: str = "Northeast",
        employees: int = 5,
        include_inventory: bool = True
    ) -> DataGenerationResult:
        """
        Generate data for a new store opening.
        
        Args:
            store_name: Name for the new store
            store_type: Type of store
            region: Geographic region
            employees: Number of employees
            include_inventory: Whether to generate initial inventory
            
        Returns:
            DataGenerationResult with store data
        """
        self.logger.info(f"Generating new store: {store_name}")
        
        result = self.store.open_new_store(
            store_name=store_name,
            store_type=store_type,
            region=region,
            initial_employees=employees,
            include_inventory=include_inventory
        )
        
        # Generate inventory if requested
        if include_inventory and result.keys.get("include_inventory"):
            store_key = result.keys["include_inventory"][0]
            inventory = self.inventory.generate_for_store(store_key)
            result.add_fact(inventory)
        
        return result
    
    def generate_promotion_campaign(
        self,
        campaign_name: str,
        start_date: date,
        end_date: date,
        discount_min: float = 0.10,
        discount_max: float = 0.30,
        products_count: int = 20
    ) -> DataGenerationResult:
        """
        Generate data for a promotion campaign.
        
        Args:
            campaign_name: Name of the campaign
            start_date: Campaign start date
            end_date: Campaign end date
            discount_min: Minimum discount percentage
            discount_max: Maximum discount percentage
            products_count: Number of products to include
            
        Returns:
            DataGenerationResult with promotion data
        """
        self.logger.info(f"Generating promotion campaign: {campaign_name}")
        
        return self.catalog.add_promotion_campaign(
            campaign_name=campaign_name,
            start_date=start_date,
            end_date=end_date,
            discount_min=discount_min,
            discount_max=discount_max,
            products_count=products_count
        )
    
    def load_keys_from_snowflake(self, connector: Any, schema: str = "ECOMMERCE_DWH") -> None:
        """
        Load existing keys from Snowflake for incremental generation.
        
        Args:
            connector: Active SnowflakeConnector instance
            schema: Schema name
        """
        self.logger.info("Loading keys from Snowflake")
        self.keys_loader.load_from_snowflake(connector, schema=schema, load_all_keys=True)
    
    def load_keys_from_cache(self, cache_path: str) -> None:
        """
        Load existing keys from cache file.
        
        Args:
            cache_path: Path to keys cache file
        """
        self.logger.info(f"Loading keys from cache: {cache_path}")
        self.keys_loader.load_from_cache(cache_path)
    
    def save_keys_to_cache(self, cache_path: str) -> None:
        """
        Save current keys to cache file.
        
        Args:
            cache_path: Path for cache file
        """
        self.logger.info(f"Saving keys to cache: {cache_path}")
        self.keys_loader.save_to_cache(cache_path)
    
    def save_to_csv(
        self,
        result: DataGenerationResult,
        output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Save generated data to CSV files.
        
        Args:
            result: DataGenerationResult to save
            output_dir: Output directory (defaults to config)
            
        Returns:
            Dictionary of table_name -> file_path
        """
        output_path = Path(output_dir or self.config.paths.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        all_data = result.get_all_data()
        
        for table_name, gen_data in all_data.items():
            file_path = output_path / f"{table_name}.csv"
            gen_data.data.to_csv(file_path, index=False)
            file_paths[table_name] = str(file_path)
            self.logger.debug(f"Saved {gen_data.row_count} records to {file_path}")
        
        self.logger.info(f"Saved {len(file_paths)} CSV files to {output_path}")
        return file_paths
    
    def _validate(self, result: DataGenerationResult) -> bool:
        """
        Validate referential integrity.
        
        Args:
            result: DataGenerationResult to validate
            
        Returns:
            True if valid, False otherwise
        """
        from .relationships import ReferentialIntegrityHandler
        
        handler = ReferentialIntegrityHandler()
        all_data = result.get_all_data()
        
        if not all_data:
            return True
        
        is_valid = handler.validate(all_data)
        
        if not is_valid:
            errors = handler.get_validation_errors()
            self.logger.warning(f"Referential integrity validation found {len(errors)} issues")
            for error in errors[:5]:
                self.logger.warning(f"  {error}")
        else:
            self.logger.info("Referential integrity validation passed")
        
        return is_valid
    
    def get_load_order(self):
        """Get recommended table load order."""
        from .relationships import ReferentialIntegrityHandler
        return ReferentialIntegrityHandler().get_load_order()


# Legacy aliases for backwards compatibility
DataGenerationOrchestrator = DataGenerator
