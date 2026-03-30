"""
Unit tests for data generation module (Phase 5 architecture).

Tests the new config-driven DataGenerator with domain helpers.
"""

import pytest
import pandas as pd
from datetime import date

from src.data_generators import (
    DataGenerator,
    DataGenConfig,
    GeneratorConfig,
    GeneratedData,
    DataGenerationResult,
    ReferentialIntegrityHandler,
    load_config,
    # Entity generators
    DimCustomersGenerator,
    DimDatesGenerator,
    DimTimeGenerator,
    DimChannelsGenerator,
    DimProductsGenerator,
    FactSalesGenerator,
    # Utilities
    date_to_key,
    key_to_date,
    CustomerSelector,
)


@pytest.fixture(scope="module")
def small_config():
    """Create a small config for fast testing."""
    config = load_config()
    config.volumes.customers = 10
    config.volumes.products = 5
    config.volumes.stores = 2
    config.volumes.employees = 5
    config.volumes.promotions = 3
    config.volumes.sales = 20
    config.volumes.customer_interactions = 10
    config.volumes.loyalty_transactions = 5
    config.volumes.inventory_snapshots = 2
    config.settings.seed = 42
    return config


@pytest.fixture(scope="module")
def result(small_config):
    """Generate complete dataset using small config."""
    gen = DataGenerator(config=small_config)
    return gen.generate_initial(validate=True)


# ============================================================================
# Config Tests
# ============================================================================

class TestDataGenConfig:
    def test_load_config_returns_datagenconfig(self):
        cfg = load_config()
        assert isinstance(cfg, DataGenConfig)
    
    def test_config_has_volumes(self):
        cfg = load_config()
        assert cfg.volumes.customers > 0
        assert cfg.volumes.products > 0
    
    def test_config_has_dates(self):
        cfg = load_config()
        assert cfg.dates.start is not None
        assert cfg.dates.end is not None
        assert cfg.dates.start < cfg.dates.end
    
    def test_config_has_settings(self):
        cfg = load_config()
        assert cfg.settings.seed is not None
        assert cfg.settings.locale == "en_US"


class TestGeneratorConfigLegacy:
    """Test legacy GeneratorConfig for backwards compatibility."""
    
    def test_generator_config_from_datagen(self):
        """Test creating GeneratorConfig from loaded DataGenConfig."""
        datagen_cfg = load_config()
        cfg = GeneratorConfig.from_datagen_config(datagen_cfg)
        # Values come from YAML
        assert cfg.num_customers == datagen_cfg.volumes.customers
        assert cfg.num_products == datagen_cfg.volumes.products
    
    def test_generator_config_to_datagen(self):
        cfg = GeneratorConfig(num_customers=100)
        datagen_cfg = cfg.to_datagen_config()
        assert datagen_cfg.volumes.customers == 100


# ============================================================================
# Dimension Generator Tests
# ============================================================================

class TestDimDatesGenerator:
    def test_generates_full_year(self, small_config):
        gen = DimDatesGenerator(small_config)
        data = gen.generate()
        # 2024 is a leap year = 366 days
        assert data.row_count == 366
    
    def test_date_key_format(self, small_config):
        gen = DimDatesGenerator(small_config)
        data = gen.generate()
        # First date key should be 20240101
        assert data.data.iloc[0]["date_key"] == 20240101
    
    def test_has_calendar_attributes(self, small_config):
        gen = DimDatesGenerator(small_config)
        data = gen.generate()
        assert "day_of_week" in data.data.columns
        assert "month_name" in data.data.columns
        assert "is_weekend" in data.data.columns


class TestDimTimeGenerator:
    def test_generates_96_intervals(self, small_config):
        gen = DimTimeGenerator(small_config)
        data = gen.generate(interval_minutes=15)
        # 24 hours * 4 intervals per hour = 96
        assert data.row_count == 96
    
    def test_time_key_format(self, small_config):
        gen = DimTimeGenerator(small_config)
        data = gen.generate()
        # First time key should be 0 (midnight)
        assert data.data.iloc[0]["time_key"] == 0


class TestDimChannelsGenerator:
    def test_generates_standard_channels(self, small_config):
        gen = DimChannelsGenerator(small_config)
        data = gen.generate()
        assert data.row_count == 6  # Standard channels


class TestDimCustomersGenerator:
    def test_generates_customers(self, small_config):
        gen = DimCustomersGenerator(small_config)
        data = gen.generate(count=10)
        assert data.row_count == 10
    
    def test_has_scd2_columns(self, small_config):
        gen = DimCustomersGenerator(small_config)
        data = gen.generate(count=1)
        assert "effective_date" in data.data.columns
        assert "end_date" in data.data.columns
        assert "is_current" in data.data.columns
    
    def test_has_profile_columns(self, small_config):
        gen = DimCustomersGenerator(small_config)
        data = gen.generate(count=1)
        assert "first_name" in data.data.columns
        assert "email" in data.data.columns
        assert "segment_key" in data.data.columns


# ============================================================================
# Fact Generator Tests
# ============================================================================

class TestFactSalesGenerator:
    def test_generates_sales(self, small_config):
        gen = FactSalesGenerator(small_config)
        data = gen.generate(count=10)
        assert data.row_count == 10
    
    def test_sales_has_amounts(self, small_config):
        gen = FactSalesGenerator(small_config)
        data = gen.generate(count=1)
        df = data.data
        assert "gross_amount" in df.columns
        assert "discount_amount" in df.columns
        assert "net_amount" in df.columns
        assert "tax_amount" in df.columns


# ============================================================================
# Full Generation Tests
# ============================================================================

class TestDataGenerator:
    def test_generates_all_tables(self, result):
        all_data = result.get_all_data()
        # 15 dimension tables + 4 fact tables + 3 bridge tables + 1 bridge-fact = 23
        assert len(all_data) == 23
    
    def test_generates_dimensions(self, result):
        assert "dim_customers" in result.dimensions
        assert "dim_products" in result.dimensions
        assert "dim_dates" in result.dimensions
    
    def test_generates_facts(self, result):
        assert "fact_sales" in result.facts
        assert "fact_inventory_snapshots" in result.facts
    
    def test_generates_bridges(self, result):
        assert "bridge_order_items" in result.facts
        assert "bridge_product_promotions" in result.facts
    
    def test_customer_count_matches_config(self, result, small_config):
        df = result.get_dataframe("dim_customers")
        assert len(df) == small_config.volumes.customers
    
    def test_sales_count_matches_config(self, result, small_config):
        df = result.get_dataframe("fact_sales")
        assert len(df) == small_config.volumes.sales


class TestDataGeneratorMethods:
    def test_generate_incremental(self, small_config):
        gen = DataGenerator(config=small_config)
        # Need some base data first
        gen.generate_initial(validate=False)
        
        # Generate incremental with date range
        result = gen.generate_incremental(
            start_date=date(2024, 6, 15),
            end_date=date(2024, 6, 20)
        )
        assert result.total_records > 0
    
    def test_generate_inventory_snapshot(self, small_config):
        gen = DataGenerator(config=small_config)
        gen.generate_initial(validate=False)
        
        data = gen.generate_inventory_snapshot(date(2024, 6, 15))
        assert data.row_count > 0


# ============================================================================
# Referential Integrity Tests
# ============================================================================

class TestReferentialIntegrityHandler:
    def test_validates_result(self, result):
        handler = ReferentialIntegrityHandler()
        all_data = result.get_all_data()
        is_valid = handler.validate(all_data)
        # Should be valid since we generated with proper order
        assert is_valid
    
    def test_get_table_dependencies(self):
        handler = ReferentialIntegrityHandler()
        deps = handler.get_table_dependencies("fact_sales")
        assert "dim_customers" in deps
        assert "dim_dates" in deps
    
    def test_get_dependent_tables(self):
        handler = ReferentialIntegrityHandler()
        children = handler.get_dependent_tables("dim_customers")
        assert "fact_sales" in children
    
    def test_get_load_order(self):
        handler = ReferentialIntegrityHandler()
        order = handler.get_load_order()
        # Dimensions before facts
        assert order.index("dim_dates") < order.index("fact_sales")
        assert order.index("dim_customers") < order.index("fact_sales")


# ============================================================================
# GeneratedData Container Tests
# ============================================================================

class TestGeneratedData:
    def test_row_count(self):
        df = pd.DataFrame({"key": [1, 2, 3]})
        data = GeneratedData(table_name="test", data=df)
        assert data.row_count == 3
    
    def test_surrogate_keys(self):
        df = pd.DataFrame({"key": [1, 2]})
        data = GeneratedData(table_name="test", data=df, surrogate_keys=[1, 2])
        assert data.surrogate_keys == [1, 2]


class TestDataGenerationResult:
    def test_add_dimension(self):
        result = DataGenerationResult()
        df = pd.DataFrame({"key": [1]})
        data = GeneratedData(table_name="dim_test", data=df, surrogate_keys=[1])
        result.add_dimension(data)
        
        assert "dim_test" in result.dimensions
        assert result.keys["dim_test"] == [1]
    
    def test_add_fact(self):
        result = DataGenerationResult()
        df = pd.DataFrame({"key": [1, 2]})
        data = GeneratedData(table_name="fact_test", data=df, surrogate_keys=[1, 2])
        result.add_fact(data)
        
        assert "fact_test" in result.facts
    
    def test_merge(self):
        result1 = DataGenerationResult()
        result2 = DataGenerationResult()
        
        df1 = pd.DataFrame({"key": [1]})
        df2 = pd.DataFrame({"key": [2]})
        
        result1.add_dimension(GeneratedData("dim_a", df1))
        result2.add_dimension(GeneratedData("dim_b", df2))
        
        result1.merge(result2)
        
        assert "dim_a" in result1.dimensions
        assert "dim_b" in result1.dimensions


# ============================================================================
# Utility Tests
# ============================================================================

class TestDateKeyUtilities:
    def test_date_to_key(self):
        d = date(2024, 1, 15)
        key = date_to_key(d)
        assert key == 20240115
    
    def test_key_to_date(self):
        key = 20240115
        d = key_to_date(key)
        assert d == date(2024, 1, 15)
    
    def test_roundtrip(self):
        original = date(2024, 7, 4)
        key = date_to_key(original)
        result = key_to_date(key)
        assert original == result


class TestCustomerSelector:
    def test_selects_from_existing(self):
        selector = CustomerSelector(
            existing_keys=[1, 2, 3],
            new_keys=[],
            existing_ratio=1.0
        )
        key = selector.select()
        assert key in [1, 2, 3]
    
    def test_selects_from_new(self):
        selector = CustomerSelector(
            existing_keys=[],
            new_keys=[100, 101],
            existing_ratio=0.0
        )
        key = selector.select()
        assert key in [100, 101]
    
    def test_ratio_based_selection(self):
        selector = CustomerSelector(
            existing_keys=[1],
            new_keys=[100],
            existing_ratio=0.8
        )
        # Select many times
        keys = selector.select_many(100)
        existing_count = sum(1 for k in keys if k == 1)
        # Should be roughly 80% existing
        assert 60 < existing_count < 95
    
    def test_has_keys(self):
        selector = CustomerSelector(existing_keys=[1], new_keys=[])
        assert selector.has_keys()
        
        empty_selector = CustomerSelector(existing_keys=[], new_keys=[])
        assert not empty_selector.has_keys()


# ============================================================================
# Seed Consistency Tests
# ============================================================================

class TestSeedConsistency:
    def test_same_seed_same_data(self):
        from faker import Faker
        
        # Reset Faker seed before each generation
        cfg1 = load_config()
        cfg1.settings.seed = 42
        cfg1.volumes.customers = 5
        Faker.seed(42)  # Reset global seed
        gen1 = DimCustomersGenerator(cfg1)
        data1 = gen1.generate(count=5)
        first_name_1 = data1.data.iloc[0]["first_name"]
        
        # Reset again for second generation
        cfg2 = load_config()
        cfg2.settings.seed = 42
        cfg2.volumes.customers = 5
        Faker.seed(42)  # Reset global seed
        gen2 = DimCustomersGenerator(cfg2)
        data2 = gen2.generate(count=5)
        first_name_2 = data2.data.iloc[0]["first_name"]
        
        # First names should match
        assert first_name_1 == first_name_2
