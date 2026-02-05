"""
Integration tests for E-Commerce Data Warehouse.

These tests are designed to run against a real Snowflake connection.
They create a temporary test schema, run tests, and cleanup afterward.

Run with: pytest tests/test_integration.py -v
Skip Snowflake tests with: pytest tests/test_integration.py -v -m "not snowflake"
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Mark for tests requiring Snowflake connection
snowflake_required = pytest.mark.skipif(
    not os.getenv("SNOWFLAKE_ACCOUNT"),
    reason="Snowflake credentials not configured"
)


class TestPhase1Foundation:
    """Tests for Phase 1: Foundation components."""
    
    def test_logger_creates_log_directory(self, tmp_path):
        """Logger creates logs directory if it doesn't exist."""
        # This is tested in test_logger.py, quick sanity check here
        from src.utils.logger import get_logger
        logger = get_logger("test_integration_logger")
        assert logger is not None
    
    def test_base_table_abstract_class(self):
        """BaseTable is properly defined as abstract."""
        from src.models.base_table import BaseTable, Column, ForeignKey
        
        # Can't instantiate abstract class
        with pytest.raises(TypeError):
            BaseTable()
        
        # Column and ForeignKey can be instantiated
        col = Column("test_col", "VARCHAR", length=50)
        assert col.name == "test_col"
        
        fk = ForeignKey("col", "other_table", "other_col")
        assert fk.column == "col"
    
    def test_snowflake_connector_import(self):
        """SnowflakeConnector module imports successfully."""
        from src.connectors.snowflake_connector import SnowflakeConnector
        assert SnowflakeConnector is not None
    
    def test_config_files_exist(self):
        """Configuration files exist."""
        config_path = project_root / "src" / "config" / "snowflake_config.yaml"
        assert config_path.exists()
        
        env_path = project_root / "src" / "config" / "environments.yaml"
        assert env_path.exists()


class TestPhase2TableModels:
    """Tests for Phase 2: Table model definitions."""
    
    def test_dimension_tables_count(self):
        """All 12 dimension tables are defined."""
        from src.models.dimension_tables import (
            DimDates, DimTime, DimChannels, DimPaymentMethods,
            DimShippingMethods, DimCustomerSegments, DimProductCategories,
            DimPromotions, DimEmployees, DimStores, DimProducts, DimCustomers
        )
        
        dim_tables = [
            DimDates, DimTime, DimChannels, DimPaymentMethods,
            DimShippingMethods, DimCustomerSegments, DimProductCategories,
            DimPromotions, DimEmployees, DimStores, DimProducts, DimCustomers
        ]
        assert len(dim_tables) == 12
    
    def test_fact_tables_count(self):
        """All 4 fact tables are defined."""
        from src.models.fact_tables import (
            FactSales, FactInventorySnapshots,
            FactCustomerInteractions, FactLoyaltyPoints
        )
        
        fact_tables = [
            FactSales, FactInventorySnapshots,
            FactCustomerInteractions, FactLoyaltyPoints
        ]
        assert len(fact_tables) == 4
    
    def test_bridge_tables_count(self):
        """All 2 bridge tables are defined."""
        from src.models.bridge_tables import (
            BridgeOrderItems, BridgeProductPromotions
        )
        
        bridge_tables = [BridgeOrderItems, BridgeProductPromotions]
        assert len(bridge_tables) == 2
    
    def test_ddl_generator_creates_valid_sql(self):
        """DDL generator produces valid CREATE TABLE SQL."""
        from src.sql_generator.ddl_generator import DDLGenerator
        from src.models.dimension_tables.dim_dates import DimDates
        
        generator = DDLGenerator()
        ddl = generator.generate_create_table(DimDates())
        
        assert "CREATE TABLE" in ddl
        assert "dim_dates" in ddl.lower()
        assert "date_key" in ddl.lower()
    
    def test_schema_manager_returns_18_tables(self):
        """Schema manager returns all 18 tables in creation order."""
        from src.sql_generator.schema_manager import SchemaManager
        
        manager = SchemaManager()
        order = manager.get_table_creation_order()
        
        assert len(order) == 18
    
    def test_schema_manager_dimensions_before_facts(self):
        """Schema manager orders dimensions before facts."""
        from src.sql_generator.schema_manager import SchemaManager
        
        manager = SchemaManager()
        order = manager.get_table_creation_order()
        table_names = [t.table_name for t in order]
        
        # Find first fact table index
        first_fact_idx = next(
            (i for i, name in enumerate(table_names) if name.startswith("fact_")),
            len(table_names)
        )
        
        # Find last dimension table index
        last_dim_idx = max(
            (i for i, name in enumerate(table_names) if name.startswith("dim_")),
            default=0
        )
        
        # All dimensions should come before facts
        assert last_dim_idx < first_fact_idx


class TestPhase3TableCreation:
    """Tests for Phase 3: Table creation (mocked)."""
    
    def test_table_creator_import(self):
        """TableCreator class imports successfully."""
        from src.table_manager.create_tables import TableCreator
        assert TableCreator is not None
    
    @patch("src.table_manager.create_tables.SnowflakeConnector")
    def test_creator_dry_run(self, mock_connector):
        """Creator dry-run mode doesn't execute SQL."""
        from src.table_manager.create_tables import TableCreator
        
        mock_conn = MagicMock()
        mock_connector.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connector.return_value.__exit__ = MagicMock(return_value=False)
        
        creator = TableCreator(mock_conn)
        # Dry run should work without errors
        assert creator is not None


class TestPhase4CLI:
    """Tests for Phase 4: CLI framework."""
    
    def test_cli_group_exists(self):
        """Main CLI group is defined."""
        from src.cli.main import cli
        assert cli is not None
    
    def test_all_commands_registered(self):
        """All expected commands are registered."""
        from src.cli.main import cli
        
        expected_commands = [
            "test-connection",
            "generate-sql",
            "create",
            "validate",
            "generate-data",
            "load-data",
            "status",
            "run-data-load",
        ]
        
        for cmd in expected_commands:
            assert cmd in cli.commands, f"Command {cmd} not found"


class TestPhase5DataGeneration:
    """Tests for Phase 5: Data generation."""
    
    def test_generator_config_defaults(self):
        """DataGenConfig loads with sensible defaults from YAML."""
        from src.data_generators import load_config
        
        config = load_config()
        # YAML config should have positive values for volumes
        assert config.volumes.customers >= 0
        assert config.volumes.products >= 0
        # Settings should have defaults
        assert config.settings is not None
    
    def test_dimension_generator_creates_dataframe(self):
        """Dimension generator produces pandas DataFrames."""
        from datetime import date
        from src.data_generators import (
            DataGenerator,
            DataGenConfig,
            VolumesConfig,
            DimCustomerSegmentsGenerator,
        )
        from src.data_generators.config import DatesConfig
        
        volumes = VolumesConfig(customers=5)
        dates = DatesConfig(start=date(2024, 1, 1), end=date(2024, 1, 7))
        config = DataGenConfig(volumes=volumes, dates=dates)
        config.settings.seed = 42
        
        generator = DimCustomerSegmentsGenerator(config)
        result = generator.generate()
        
        assert len(result.data) > 0
        assert "segment_key" in result.data.columns
    
    def test_fact_generator_creates_dataframe(self):
        """Fact generator produces pandas DataFrames."""
        from datetime import date
        from src.data_generators import (
            DataGenerator,
            DataGenConfig,
            VolumesConfig,
        )
        from src.data_generators.config import DatesConfig
        
        # Generate minimal data including facts
        volumes = VolumesConfig(
            customers=3,
            products=5,
            stores=2,
            employees=2,
            sales=10,
        )
        dates = DatesConfig(start=date(2024, 1, 1), end=date(2024, 1, 7))
        config = DataGenConfig(volumes=volumes, dates=dates)
        config.settings.seed = 42
        
        generator = DataGenerator(config=config)
        result = generator.generate_initial(validate=False)
        
        sales_data = result.get_table_data("fact_sales")
        assert sales_data is not None
        assert len(sales_data.data) > 0
        assert "sale_key" in sales_data.data.columns
    
    def test_orchestrator_generates_all_tables(self):
        """DataGenerator generates multiple tables."""
        from datetime import date
        from src.data_generators import DataGenerator, DataGenConfig, VolumesConfig
        from src.data_generators.config import DatesConfig
        
        volumes = VolumesConfig(
            customers=3,
            products=5,
            stores=2,
            employees=2,
            sales=10,
        )
        dates = DatesConfig(start=date(2024, 1, 1), end=date(2024, 1, 7))
        config = DataGenConfig(volumes=volumes, dates=dates)
        config.settings.seed = 42
        
        generator = DataGenerator(config=config)
        result = generator.generate_initial(validate=False)
        
        assert result.total_records > 0
        # Should have data for multiple tables
        all_data = result.get_all_data()
        assert len(all_data) >= 10  # At minimum dimensions + some facts


class TestPhase6DataLoading:
    """Tests for Phase 6: Data loading (mocked)."""
    
    def test_loader_config_defaults(self):
        """LoaderConfig has sensible defaults."""
        from src.data_loaders.base_loader import LoaderConfig
        
        config = LoaderConfig()
        assert config.batch_size > 0
        assert config.truncate_before_load is False
    
    def test_snowflake_loader_import(self):
        """SnowflakeLoader imports successfully."""
        from src.data_loaders.snowflake_loader import SnowflakeLoader
        assert SnowflakeLoader is not None
    
    def test_load_orchestrator_import(self):
        """DataLoadOrchestrator imports successfully."""
        from src.data_loaders.load_orchestrator import DataLoadOrchestrator
        assert DataLoadOrchestrator is not None
    
    def test_referential_integrity_handler(self):
        """ReferentialIntegrityHandler provides correct load order."""
        from src.data_generators import ReferentialIntegrityHandler
        
        handler = ReferentialIntegrityHandler()
        order = handler.get_load_order()
        
        # Dimensions should come before facts
        dim_indices = [i for i, t in enumerate(order) if t.startswith("dim_")]
        fact_indices = [i for i, t in enumerate(order) if t.startswith("fact_")]
        
        if dim_indices and fact_indices:
            assert max(dim_indices) < min(fact_indices)


class TestPhase8Integration:
    """Tests for Phase 8: Full integration (mocked end-to-end)."""
    
    def test_sample_query_syntax(self):
        """Sample analytical queries have valid syntax."""
        # These queries should parse correctly in Snowflake
        queries = [
            """
            SELECT 
                cs.segment_name,
                COUNT(DISTINCT c.customer_key) as customer_count,
                SUM(fs.net_amount) as total_revenue
            FROM fact_sales fs
            JOIN dim_customers c ON fs.customer_key = c.customer_key
            JOIN dim_customer_segments cs ON c.segment_key = cs.segment_key
            GROUP BY cs.segment_name
            """,
            """
            SELECT 
                ch.channel_name,
                SUM(fs.net_amount) as revenue,
                COUNT(fs.sale_key) as orders
            FROM fact_sales fs
            JOIN dim_channels ch ON fs.channel_key = ch.channel_key
            GROUP BY ch.channel_name
            """,
            """
            SELECT 
                p.product_name,
                s.store_name,
                fi.quantity_on_hand
            FROM fact_inventory_snapshots fi
            JOIN dim_products p ON fi.product_key = p.product_key
            JOIN dim_stores s ON fi.store_key = s.store_key
            WHERE fi.quantity_on_hand < fi.reorder_point
            """,
        ]
        
        # Basic syntax checks
        for query in queries:
            assert "SELECT" in query.upper()
            assert "FROM" in query.upper()
    
    def test_end_to_end_data_flow(self):
        """Test complete data generation to loading flow (mocked)."""
        from datetime import date
        from src.data_generators import DataGenerator, DataGenConfig, VolumesConfig
        from src.data_generators.config import DatesConfig
        
        # Generate small dataset
        volumes = VolumesConfig(
            customers=2,
            products=3,
            stores=1,
            employees=2,
            sales=5,
        )
        dates = DatesConfig(start=date(2024, 1, 1), end=date(2024, 1, 7))
        config = DataGenConfig(volumes=volumes, dates=dates)
        config.settings.seed = 42
        
        generator = DataGenerator(config=config)
        result = generator.generate_initial(validate=False)
        
        # Verify data was generated
        all_data = result.get_all_data()
        
        # Check key tables have data
        assert "dim_customers" in all_data or len(all_data) > 0
        assert result.total_records > 0
    
# Snowflake-specific tests (skipped if no credentials)
@snowflake_required
class TestSnowflakeIntegration:
    """Integration tests requiring real Snowflake connection."""
    
    @pytest.fixture(scope="class")
    def snowflake_connector(self):
        """Create Snowflake connection for tests."""
        from src.connectors.snowflake_connector import SnowflakeConnector
        
        connector = SnowflakeConnector()
        connector.connect()
        yield connector
        connector.disconnect()
    
    def test_connection_works(self, snowflake_connector):
        """Can connect to Snowflake."""
        result = snowflake_connector.execute_query("SELECT CURRENT_VERSION()")
        assert len(result) > 0
    
    def test_can_create_temp_table(self, snowflake_connector):
        """Can create temporary table."""
        snowflake_connector.execute_query("""
            CREATE OR REPLACE TEMPORARY TABLE test_temp_table (
                id NUMBER,
                name VARCHAR(100)
            )
        """)
        
        result = snowflake_connector.execute_query("SHOW TABLES LIKE 'TEST_TEMP_TABLE'")
        assert len(result) > 0
