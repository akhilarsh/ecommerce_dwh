"""
Unit tests for data loading module.

Tests BaseDataLoader interface, SnowflakeLoader (mocked), and DataLoadOrchestrator.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import tempfile

import pandas as pd
import pytest

from src.data_loaders import (
    BaseDataLoader,
    DataLoadOrchestrator,
    LoaderConfig,
    LoadMethod,
    LoadProgress,
    LoadResult,
    LoadSummary,
    SnowflakeLoader,
)
from src.data_generators import (
    DataGenerator,
    DataGenConfig,
    DataGenerationResult,
    VolumesConfig,
)


# =============================================================================
# LoadResult Tests
# =============================================================================

class TestLoadResult:
    """Tests for LoadResult dataclass."""
    
    def test_successful_result(self):
        """Test successful load result."""
        result = LoadResult(
            table_name="dim_customers",
            rows_loaded=1,
            success=True,
            method=LoadMethod.DATAFRAME
        )
        assert result.success
        assert result.rows_loaded == 1
        assert not result.has_errors
    
    def test_failed_result_with_errors(self):
        """Test failed load result with errors."""
        result = LoadResult(
            table_name="dim_customers",
            rows_loaded=0,
            success=False,
            method=LoadMethod.DATAFRAME,
            errors=["Connection failed", "Timeout"]
        )
        assert not result.success
        assert result.has_errors
        assert len(result.errors) == 2
    
    def test_result_string_representation(self):
        """Test string representation of result."""
        result = LoadResult(
            table_name="dim_customers",
            rows_loaded=1,
            success=True,
            method=LoadMethod.DATAFRAME,
            duration_seconds=1.5
        )
        str_repr = str(result)
        assert "dim_customers" in str_repr
        assert "SUCCESS" in str_repr
        assert "1 rows" in str_repr


# =============================================================================
# LoadSummary Tests
# =============================================================================

class TestLoadSummary:
    """Tests for LoadSummary dataclass."""
    
    def test_empty_summary(self):
        """Test empty summary."""
        summary = LoadSummary()
        assert summary.total_rows == 0
        assert summary.total_tables == 0
        assert summary.all_successful
    
    def test_summary_with_results(self):
        """Test summary with multiple results."""
        summary = LoadSummary(
            results=[
                LoadResult("dim_customers", 1, True, LoadMethod.DATAFRAME),
                LoadResult("dim_products", 1, True, LoadMethod.DATAFRAME),
                LoadResult("fact_sales", 0, False, LoadMethod.DATAFRAME, errors=["Error"]),
            ],
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        assert summary.total_tables == 3
        assert summary.successful_tables == 2
        assert summary.failed_tables == 1
        assert summary.total_rows == 2
        assert not summary.all_successful
    
    def test_get_failed_results(self):
        """Test getting failed results."""
        summary = LoadSummary(
            results=[
                LoadResult("dim_customers", 1, True, LoadMethod.DATAFRAME),
                LoadResult("fact_sales", 0, False, LoadMethod.DATAFRAME),
            ]
        )
        failed = summary.get_failed_results()
        assert len(failed) == 1
        assert failed[0].table_name == "fact_sales"


# =============================================================================
# LoaderConfig Tests
# =============================================================================

class TestLoaderConfig:
    """Tests for LoaderConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LoaderConfig()
        assert config.batch_size == 10000
        assert config.truncate_before_load is False
        assert config.validate_after_load is True
        assert config.staged_load_threshold == 100000
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LoaderConfig(
            batch_size=5000,
            truncate_before_load=True,
            staged_load_threshold=50000
        )
        assert config.batch_size == 5000
        assert config.truncate_before_load is True
        assert config.staged_load_threshold == 50000
    
    def test_invalid_batch_size(self):
        """Test validation of batch_size."""
        with pytest.raises(ValueError, match="batch_size"):
            LoaderConfig(batch_size=0)


# =============================================================================
# LoadProgress Tests
# =============================================================================

class TestLoadProgress:
    """Tests for LoadProgress dataclass."""
    
    def test_initial_progress(self):
        """Test initial progress state."""
        progress = LoadProgress()
        assert progress.table_progress == 0.0
        assert progress.row_progress == 0.0
    
    def test_progress_calculation(self):
        """Test progress percentage calculation."""
        progress = LoadProgress(
            total_tables=10,
            loaded_tables=5,
            total_rows=1000,
            loaded_rows=500
        )
        assert progress.table_progress == 50.0
        assert progress.row_progress == 50.0


# =============================================================================
# SnowflakeLoader Tests (Mocked)
# =============================================================================

class TestSnowflakeLoader:
    """Tests for SnowflakeLoader with mocked Snowflake connection."""
    
    @pytest.fixture
    def mock_connector(self):
        """Create a mocked SnowflakeConnector."""
        connector = MagicMock()
        connector.database = "ECOMMERCE_DWH"
        connector.schema = "PUBLIC"
        connector.connection = MagicMock()
        connector.execute_query = MagicMock(return_value=[])
        return connector
    
    @pytest.fixture
    def loader(self, mock_connector):
        """Create SnowflakeLoader with mocked connector."""
        return SnowflakeLoader(mock_connector)
    
    def test_platform_name(self, loader):
        """Test platform name."""
        assert loader.platform_name == "snowflake"
    
    def test_config_inherits_from_connector(self, mock_connector):
        """Test that config inherits database/schema from connector."""
        loader = SnowflakeLoader(mock_connector)
        assert loader.config.database == "ECOMMERCE_DWH"
        assert loader.config.schema == "PUBLIC"
    
    @patch("snowflake.connector.pandas_tools.write_pandas")
    def test_load_dataframe_success(self, mock_write_pandas, loader):
        """Test successful DataFrame load."""
        mock_write_pandas.return_value = (True, 1, 1, None)
        
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        result = loader.load_dataframe(df, "test_table")
        
        assert result.success
        assert result.rows_loaded == 1
        assert result.method == LoadMethod.DATAFRAME
        mock_write_pandas.assert_called_once()
    
    def test_load_empty_dataframe(self, loader):
        """Test loading empty DataFrame."""
        df = pd.DataFrame()
        result = loader.load_dataframe(df, "test_table")
        
        assert not result.success
        assert result.has_errors
        assert "empty" in result.errors[0].lower()
    
    def test_truncate_table(self, loader, mock_connector):
        """Test table truncation."""
        loader.truncate_table("dim_customers")
        
        mock_connector.execute_query.assert_called()
        call_args = mock_connector.execute_query.call_args[0][0]
        assert "TRUNCATE TABLE" in call_args
        assert "DIM_CUSTOMERS" in call_args
    
    def test_get_row_count(self, loader, mock_connector):
        """Test getting row count."""
        mock_connector.execute_query.return_value = [(1,)]
        
        count = loader.get_row_count("dim_customers")
        
        assert count == 1
        mock_connector.execute_query.assert_called()
    
    def test_table_exists(self, loader, mock_connector):
        """Test checking if table exists."""
        mock_connector.execute_query.return_value = [(1,)]
        
        exists = loader.table_exists("dim_customers")
        
        assert exists
        mock_connector.execute_query.assert_called()


# =============================================================================
# DataLoadOrchestrator Tests
# =============================================================================

class TestDataLoadOrchestrator:
    """Tests for DataLoadOrchestrator."""
    
    @pytest.fixture
    def mock_loader(self):
        """Create a mocked BaseDataLoader."""
        loader = MagicMock(spec=BaseDataLoader)
        loader.config = LoaderConfig()
        loader._select_load_method = MagicMock(return_value=LoadMethod.DATAFRAME)
        loader.load_dataframe = MagicMock(
            side_effect=lambda df, name: LoadResult(
                table_name=name,
                rows_loaded=len(df),
                success=True,
                method=LoadMethod.DATAFRAME
            )
        )
        loader.load = MagicMock(
            side_effect=lambda data, name: LoadResult(
                table_name=name,
                rows_loaded=len(data) if hasattr(data, '__len__') else 1,
                success=True,
                method=LoadMethod.DATAFRAME
            )
        )
        loader.table_exists = MagicMock(return_value=True)
        loader.get_row_count = MagicMock(return_value=1)
        return loader
    
    @pytest.fixture
    def orchestrator(self, mock_loader):
        """Create DataLoadOrchestrator with mocked loader."""
        return DataLoadOrchestrator(mock_loader)
    
    def test_get_load_order(self, orchestrator):
        """Test that load order is retrieved correctly."""
        order = orchestrator.get_load_order()
        
        assert len(order) == 20
        # Dimensions should come before facts
        dim_dates_idx = order.index("dim_dates")
        fact_sales_idx = order.index("fact_sales")
        assert dim_dates_idx < fact_sales_idx
        
        # Bridge tables should come last
        bridge_idx = order.index("bridge_order_items")
        assert bridge_idx > fact_sales_idx
    
    def test_load_from_dataframes(self, orchestrator, mock_loader):
        """Test loading from dictionary of DataFrames."""
        dataframes = {
            "dim_customers": pd.DataFrame({"id": [1]}),
            "dim_products": pd.DataFrame({"id": [1]}),
        }
        
        summary = orchestrator.load_from_dataframes(dataframes)
        
        assert summary.total_tables == 2
        assert summary.all_successful
        assert mock_loader.load_dataframe.call_count == 2
    
    def test_load_from_csv_directory(self, orchestrator, mock_loader):
        """Test loading from CSV directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test CSV files
            df = pd.DataFrame({"id": [1], "name": ["test"]})
            df.to_csv(Path(tmpdir) / "dim_customers.csv", index=False)
            df.to_csv(Path(tmpdir) / "dim_products.csv", index=False)
            
            summary = orchestrator.load_from_csv_directory(tmpdir)
            
            assert summary.total_tables == 2
            assert summary.all_successful
    
    def test_load_single_table(self, orchestrator, mock_loader):
        """Test loading a single table."""
        df = pd.DataFrame({"id": [1]})
        result = orchestrator.load_single_table("dim_customers", df)
        
        assert result.success
        assert result.table_name == "dim_customers"
        mock_loader.load.assert_called_once()
    
    def test_progress_callback(self, orchestrator, mock_loader):
        """Test progress callback is called."""
        callback = MagicMock()
        orchestrator.set_progress_callback(callback)
        
        dataframes = {
            "dim_customers": pd.DataFrame({"id": [1]}),
        }
        
        orchestrator.load_from_dataframes(dataframes)
        
        callback.assert_called()
        progress = callback.call_args[0][0]
        assert isinstance(progress, LoadProgress)
    
    def test_load_from_generation_result(self, orchestrator, mock_loader):
        """Test loading from DataGenerationResult."""
        from datetime import date
        from src.data_generators.config import DatesConfig
        
        # Generate minimal test data
        volumes = VolumesConfig(
            customers=1,
            products=1,
            stores=1,
            employees=1,
            sales=1,
        )
        dates = DatesConfig(
            start=date(2024, 1, 1),
            end=date(2024, 1, 7),  # 1 week for minimal test
        )
        config = DataGenConfig(volumes=volumes, dates=dates)
        generator = DataGenerator(config=config)
        result = generator.generate_initial(validate=False)
        
        summary = orchestrator.load_from_generation_result(result)
        
        assert summary.total_tables > 0
        assert summary.all_successful
    
    def test_verify_load(self, orchestrator, mock_loader):
        """Test load verification."""
        mock_loader.get_row_count.return_value = 1
        
        verification = orchestrator.verify_load(
            expected_counts={"dim_customers": 1}
        )
        
        assert "dim_customers" in verification
        assert verification["dim_customers"]["actual"] == 1
        assert verification["dim_customers"]["match"] is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestLoaderIntegration:
    """Integration tests for the data loading pipeline."""
    
    def test_full_pipeline_with_mocked_loader(self):
        """Test full pipeline: generate -> load (mocked)."""
        from datetime import date
        from src.data_generators.config import DatesConfig
        
        # Generate data
        volumes = VolumesConfig(
            customers=1,
            products=1,
            stores=1,
            employees=1,
            sales=1,
        )
        dates = DatesConfig(
            start=date(2024, 1, 1),
            end=date(2024, 1, 7),  # 1 week for minimal test
        )
        config = DataGenConfig(volumes=volumes, dates=dates)
        generator = DataGenerator(config=config)
        gen_result = generator.generate_initial(validate=False)
        
        # Create mocked loader
        mock_loader = MagicMock(spec=BaseDataLoader)
        mock_loader.config = LoaderConfig()
        mock_loader._select_load_method = MagicMock(return_value=LoadMethod.DATAFRAME)
        mock_loader.load_dataframe = MagicMock(
            side_effect=lambda df, name: LoadResult(
                table_name=name,
                rows_loaded=len(df),
                success=True,
                method=LoadMethod.DATAFRAME
            )
        )
        
        # Load data
        load_orchestrator = DataLoadOrchestrator(mock_loader)
        summary = load_orchestrator.load_from_generation_result(gen_result)
        
        # Verify - at least 10 tables (depends on config volumes)
        assert summary.total_tables >= 10
        assert summary.all_successful
        assert summary.total_rows >= 10
