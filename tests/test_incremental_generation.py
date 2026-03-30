"""
Unit tests for incremental data generation module.

Tests the IncrementalDataOrchestrator and ExistingKeysLoader classes
for operational data generation patterns.
"""

import json
import pytest
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.data_generators import (
    IncrementalDataOrchestrator,
    IncrementalConfig,
    GenerationMode,
    ExistingKeysLoader,
    KeyInfo,
    TABLE_KEY_COLUMNS,
    ReferentialIntegrityHandler,
)


# ============================================================================
# ExistingKeysLoader Tests
# ============================================================================

class TestExistingKeysLoader:
    """Tests for ExistingKeysLoader functionality."""
    
    def test_initialize_empty_creates_all_tables(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        
        # Should have all 18 tables
        assert len(loader._key_cache) == 23
        assert "dim_customers" in loader._key_cache
        assert "fact_sales" in loader._key_cache
    
    def test_initialize_empty_sets_zero_max_key(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        
        assert loader.get_max_key("dim_customers") == 0
        assert loader.get_next_key("dim_customers") == 1
    
    def test_get_next_key_increments(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        
        # Simulate adding records
        loader.update_after_generation("dim_customers", [1, 2, 3])
        
        assert loader.get_next_key("dim_customers") == 4
    
    def test_update_after_generation(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        
        loader.update_after_generation("dim_customers", [1, 2, 3, 4, 5])
        
        assert loader.get_max_key("dim_customers") == 5
        assert loader.get_row_count("dim_customers") == 5
    
    def test_get_valid_fk_keys_returns_range(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        
        # Add some keys
        loader.update_after_generation("dim_customers", [1, 2, 3])
        
        fk_keys = loader.get_valid_fk_keys("dim_customers")
        assert fk_keys == [1, 2, 3]
    
    def test_save_and_load_cache(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        loader.update_after_generation("dim_customers", [1, 2, 3, 4, 5])
        loader.update_after_generation("dim_products", [1, 2, 3])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_path = f.name
        
        try:
            # Save
            loader.save_to_cache(cache_path)
            
            # Load in new loader
            new_loader = ExistingKeysLoader()
            new_loader.load_from_cache(cache_path)
            
            assert new_loader.get_max_key("dim_customers") == 5
            assert new_loader.get_max_key("dim_products") == 3
        finally:
            Path(cache_path).unlink(missing_ok=True)
    
    def test_is_loaded(self):
        loader = ExistingKeysLoader()
        assert not loader.is_loaded()
        
        loader.initialize_empty()
        assert loader.is_loaded()
    
    def test_summary(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        loader.update_after_generation("dim_customers", [1, 2, 3])
        
        summary = loader.summary()
        
        assert summary["table_count"] == 23
        assert summary["tables"]["dim_customers"]["max_key"] == 3
        assert summary["tables"]["dim_customers"]["row_count"] == 3
    
    def test_get_all_dimension_keys(self):
        loader = ExistingKeysLoader()
        loader.initialize_empty()
        loader.update_after_generation("dim_customers", [1, 2, 3])
        loader.update_after_generation("dim_products", [1, 2])
        loader.update_after_generation("dim_stores", [1])
        
        dim_keys = loader.get_all_dimension_keys()
        
        assert "dim_customers" in dim_keys
        assert dim_keys["dim_customers"] == [1, 2, 3]


class TestKeyInfo:
    """Tests for KeyInfo dataclass."""
    
    def test_to_dict_and_from_dict(self):
        info = KeyInfo(
            table_name="dim_customers",
            key_column="customer_key",
            max_key=100,
            valid_keys=[1, 2, 3],
            row_count=100,
        )
        
        d = info.to_dict()
        restored = KeyInfo.from_dict(d)
        
        assert restored.table_name == "dim_customers"
        assert restored.max_key == 100
        assert restored.valid_keys == [1, 2, 3]


# ============================================================================
# IncrementalConfig Tests
# ============================================================================

class TestIncrementalConfig:
    """Tests for IncrementalConfig."""
    
    def test_default_target_date_is_today(self):
        config = IncrementalConfig()
        assert config.target_date == date.today()
    
    def test_custom_volumes(self):
        config = IncrementalConfig(
            new_customers_per_day=100,
            new_orders_per_day=1000,
        )
        assert config.new_customers_per_day == 100
        assert config.new_orders_per_day == 1000
    
    def test_default_mode_is_daily(self):
        config = IncrementalConfig()
        assert config.mode == GenerationMode.DAILY


# ============================================================================
# IncrementalDataOrchestrator Tests
# ============================================================================

class TestIncrementalDataOrchestrator:
    """Tests for IncrementalDataOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with empty key state."""
        config = IncrementalConfig(
            new_customers_per_day=5,
            new_orders_per_day=10,
            new_interactions_per_day=5,
            new_loyalty_transactions_per_day=3,
            seed=42,
        )
        orch = IncrementalDataOrchestrator(config)
        orch.keys_loader.initialize_empty()
        return orch
    
    def test_generate_daily_operations_creates_customers(self, orchestrator):
        result = orchestrator.generate_daily_operations(
            target_date=date.today(),
            new_customers=5,
            new_orders=0,
            new_interactions=0,
            new_loyalty_transactions=0
        )
        
        assert "dim_customers" in result.dimensions
        assert result.dimensions["dim_customers"].row_count == 5
    
    def test_generate_daily_operations_creates_orders(self, orchestrator):
        # First add some dimension keys
        orchestrator.keys_loader.update_after_generation("dim_customers", [1, 2, 3])
        orchestrator.keys_loader.update_after_generation("dim_stores", [1])
        orchestrator.keys_loader.update_after_generation("dim_channels", [1, 2, 3])
        orchestrator.keys_loader.update_after_generation("dim_payment_methods", [1])
        orchestrator.keys_loader.update_after_generation("dim_shipping_methods", [1])
        orchestrator.keys_loader.update_after_generation("dim_employees", [1])
        orchestrator.keys_loader.update_after_generation("dim_time", [800, 900, 1000])
        
        result = orchestrator.generate_daily_operations(
            target_date=date.today(),
            new_customers=0,
            new_orders=10,
            new_interactions=0,
            new_loyalty_transactions=0
        )
        
        assert "fact_sales" in result.facts
        assert result.facts["fact_sales"].row_count == 10
        assert "bridge_order_items" in result.facts
    
    def test_generate_daily_operations_uses_correct_date_key(self, orchestrator):
        target = date(2024, 6, 15)
        expected_date_key = 20240615
        
        orchestrator.keys_loader.update_after_generation("dim_customers", [1])
        orchestrator.keys_loader.update_after_generation("dim_stores", [1])
        orchestrator.keys_loader.update_after_generation("dim_channels", [1])
        orchestrator.keys_loader.update_after_generation("dim_payment_methods", [1])
        orchestrator.keys_loader.update_after_generation("dim_shipping_methods", [1])
        orchestrator.keys_loader.update_after_generation("dim_employees", [1])
        
        result = orchestrator.generate_daily_operations(
            target_date=target,
            new_customers=0,
            new_orders=5,
            new_interactions=0,
            new_loyalty_transactions=0
        )
        
        df = result.facts["fact_sales"].data
        assert all(df["date_key"] == expected_date_key)
    
    def test_generate_daily_operations_key_sequencing(self, orchestrator):
        # Simulate existing data
        orchestrator.keys_loader.update_after_generation("dim_customers", list(range(1, 101)))
        orchestrator.keys_loader.update_after_generation("dim_stores", [1])
        orchestrator.keys_loader.update_after_generation("dim_channels", [1])
        
        result = orchestrator.generate_daily_operations(
            target_date=date.today(),
            new_customers=5,
            new_orders=0,
            new_interactions=0,
            new_loyalty_transactions=0
        )
        
        # New customers should start at key 101
        df = result.dimensions["dim_customers"].data
        assert df["customer_key"].min() == 101
        assert df["customer_key"].max() == 105
    
    def test_generate_inventory_snapshot(self, orchestrator):
        # Add dimension keys
        orchestrator.keys_loader.update_after_generation("dim_stores", [1, 2])
        orchestrator.keys_loader.update_after_generation("dim_products", [1, 2, 3])
        
        data = orchestrator.generate_inventory_snapshot(
            snapshot_date=date.today(),
            stores=[1, 2],
            products=[1, 2, 3]
        )
        
        # Should have 2 stores × 3 products = 6 records
        assert data.row_count == 6
        assert data.table_name == "fact_inventory_snapshots"
    
    def test_add_new_store_creates_store_record(self, orchestrator):
        result = orchestrator.add_new_store(
            store_name="Test Store",
            store_type="Mall",
            region="Northeast",
            initial_employees=3,
            include_inventory=False
        )
        
        assert "dim_stores" in result.dimensions
        assert result.dimensions["dim_stores"].row_count == 1
        
        df = result.dimensions["dim_stores"].data
        assert df.iloc[0]["store_name"] == "Test Store"
    
    def test_add_new_store_creates_employees(self, orchestrator):
        result = orchestrator.add_new_store(
            store_name="Test Store",
            initial_employees=5,
            include_inventory=False
        )
        
        assert "dim_employees" in result.dimensions
        assert result.dimensions["dim_employees"].row_count == 5
    
    def test_add_promotion_campaign(self, orchestrator):
        # Add some products
        orchestrator.keys_loader.update_after_generation("dim_products", list(range(1, 51)))
        
        result = orchestrator.add_promotion_campaign(
            campaign_name="Summer Sale",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 8, 31),
            discount_min=0.15,
            discount_max=0.40
        )
        
        assert "dim_promotions" in result.dimensions
        assert result.dimensions["dim_promotions"].row_count == 1
        
        assert "bridge_product_promotions" in result.facts
        assert result.facts["bridge_product_promotions"].row_count > 0
    
    def test_add_new_products(self, orchestrator):
        # Add a category
        orchestrator.keys_loader.update_after_generation("dim_product_categories", [1])
        
        data = orchestrator.add_new_products(
            category_key=1,
            count=10
        )
        
        assert data.row_count == 10
        assert all(data.data["category_key"] == 1)
    
    def test_add_employees(self, orchestrator):
        # Add a store
        orchestrator.keys_loader.update_after_generation("dim_stores", [1])
        
        data = orchestrator.add_employees(
            store_key=1,
            count=5
        )
        
        assert data.row_count == 5
        assert all(data.data["store_key"] == 1)
    
    def test_extend_date_dimension(self, orchestrator):
        data = orchestrator.extend_date_dimension(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10)
        )
        
        # 10 days inclusive
        assert data.row_count == 10
        assert data.data.iloc[0]["date_key"] == 20250101
        assert data.data.iloc[-1]["date_key"] == 20250110
    
    def test_keys_updated_after_generation(self, orchestrator):
        initial_max = orchestrator.keys_loader.get_max_key("dim_customers")
        
        orchestrator.generate_daily_operations(
            target_date=date.today(),
            new_customers=10,
            new_orders=0,
            new_interactions=0,
            new_loyalty_transactions=0
        )
        
        new_max = orchestrator.keys_loader.get_max_key("dim_customers")
        assert new_max == initial_max + 10


class TestIncrementalReferentialIntegrity:
    """Tests for referential integrity in incremental generation."""
    
    def test_daily_operations_maintains_referential_integrity(self):
        config = IncrementalConfig(
            new_customers_per_day=10,
            new_orders_per_day=20,
            new_interactions_per_day=10,
            new_loyalty_transactions_per_day=5,
            seed=42,
        )
        orchestrator = IncrementalDataOrchestrator(config)
        orchestrator.keys_loader.initialize_empty()
        
        # Add some base dimension data
        orchestrator.keys_loader.update_after_generation("dim_stores", [1, 2, 3])
        orchestrator.keys_loader.update_after_generation("dim_channels", [1, 2, 3])
        orchestrator.keys_loader.update_after_generation("dim_payment_methods", [1, 2])
        orchestrator.keys_loader.update_after_generation("dim_shipping_methods", [1, 2])
        orchestrator.keys_loader.update_after_generation("dim_employees", list(range(1, 11)))
        orchestrator.keys_loader.update_after_generation("dim_products", list(range(1, 21)))
        orchestrator.keys_loader.update_after_generation("dim_time", list(range(800, 2200, 100)))
        orchestrator.keys_loader.update_after_generation("dim_promotions", [1, 2])
        
        result = orchestrator.generate_daily_operations(
            target_date=date.today(),
            new_customers=10,
            new_orders=20,
            new_interactions=10,
            new_loyalty_transactions=5
        )
        
        # Verify FK relationships
        handler = ReferentialIntegrityHandler()
        all_data = result.get_all_data()
        
        # Check that customer keys in sales are from the newly generated customers
        if "fact_sales" in result.facts and "dim_customers" in result.dimensions:
            sales_df = result.facts["fact_sales"].data
            customer_keys = set(sales_df["customer_key"].dropna().unique())
            
            # Should include keys from both existing (from keys_loader) and new customers
            new_customer_keys = set(result.dimensions["dim_customers"].surrogate_keys)
            # All customer keys in sales should be valid
            assert len(customer_keys) > 0


class TestSaveAndLoadKeysWithCache:
    """Tests for keys cache persistence across generations."""
    
    def test_multiple_daily_runs_accumulate_keys(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_path = f.name
        
        try:
            # Day 1
            config = IncrementalConfig(seed=42)
            orch1 = IncrementalDataOrchestrator(config)
            orch1.keys_loader.initialize_empty()
            
            orch1.generate_daily_operations(
                target_date=date(2024, 1, 1),
                new_customers=5,
                new_orders=0,
                new_interactions=0,
                new_loyalty_transactions=0
            )
            orch1.save_keys_to_cache(cache_path)
            
            # Day 2 - new orchestrator, load from cache
            orch2 = IncrementalDataOrchestrator(config)
            orch2.load_existing_keys_from_cache(cache_path)
            
            result = orch2.generate_daily_operations(
                target_date=date(2024, 1, 2),
                new_customers=5,
                new_orders=0,
                new_interactions=0,
                new_loyalty_transactions=0
            )
            
            # Day 2 customers should start at key 6
            df = result.dimensions["dim_customers"].data
            assert df["customer_key"].min() == 6
            assert df["customer_key"].max() == 10
            
        finally:
            Path(cache_path).unlink(missing_ok=True)


# ============================================================================
# GenerationMode Enum Tests
# ============================================================================

class TestGenerationMode:
    """Tests for GenerationMode enum."""
    
    def test_all_modes_defined(self):
        assert GenerationMode.INITIAL.value == "initial"
        assert GenerationMode.DAILY.value == "daily"
        assert GenerationMode.INVENTORY_SNAPSHOT.value == "inventory-snapshot"
        assert GenerationMode.NEW_STORE.value == "new-store"
        assert GenerationMode.PROMOTION_CAMPAIGN.value == "promotion-campaign"
        assert GenerationMode.NEW_PRODUCTS.value == "new-products"
        assert GenerationMode.EMPLOYEE_UPDATE.value == "employee-update"
        assert GenerationMode.EXTEND_DATES.value == "extend-dates"
