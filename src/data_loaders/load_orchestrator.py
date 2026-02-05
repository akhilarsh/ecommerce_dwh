"""
Data loading orchestrator.

Coordinates loading data into a data warehouse with FK dependency ordering,
progress tracking, and error handling. Supports resume after partial failures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type, Union

import pandas as pd

from src.data_generators import (
    DataGenerationResult,
    ReferentialIntegrityHandler,
)
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadResult,
    LoadState,
    LoadSummary,
)
from src.utils.logger import get_logger

logger = get_logger("loader.orchestrator")


@dataclass
class LoadProgress:
    """Progress tracking for data loading."""
    
    total_tables: int = 0
    loaded_tables: int = 0
    current_table: Optional[str] = None
    total_rows: int = 0
    loaded_rows: int = 0
    
    @property
    def table_progress(self) -> float:
        """Progress as percentage of tables loaded."""
        if self.total_tables == 0:
            return 0.0
        return (self.loaded_tables / self.total_tables) * 100
    
    @property
    def row_progress(self) -> float:
        """Progress as percentage of rows loaded."""
        if self.total_rows == 0:
            return 0.0
        return (self.loaded_rows / self.total_rows) * 100


class DataLoadOrchestrator:
    """
    Orchestrates data loading into a data warehouse.
    
    Features:
    - Loads tables in FK dependency order
    - Supports loading from CSV files or DataFrames
    - Progress tracking with callbacks
    - Transaction management
    - Error handling with continue/abort options
    - Resume capability after partial failures
    
    Usage:
        with SnowflakeConnector() as connector:
            loader = SnowflakeLoader(connector)
            orchestrator = DataLoadOrchestrator(loader)
            
            # Load from CSV directory
            summary = orchestrator.load_from_csv_directory("outputs/generated_data/")
            
            # Or load from DataGenerationResult
            summary = orchestrator.load_from_generation_result(result)
            
            # Resume after partial failure
            summary = orchestrator.load_from_csv_directory(
                "outputs/generated_data/",
                resume=True
            )
    """
    
    def __init__(
        self,
        loader: BaseDataLoader,
        config: Optional[LoaderConfig] = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            loader: Platform-specific data loader instance
            config: Override config (uses loader's config if not provided)
        """
        self.loader = loader
        self.config = config or loader.config
        self.integrity_handler = ReferentialIntegrityHandler()
        self._logger = logger
        
        # Progress tracking
        self._progress = LoadProgress()
        self._progress_callback: Optional[Callable[[LoadProgress], None]] = None
        
        # State tracking for resume capability
        self._state: Optional[LoadState] = None
    
    def set_progress_callback(
        self,
        callback: Callable[[LoadProgress], None]
    ) -> None:
        """
        Set a callback function for progress updates.
        
        Args:
            callback: Function called with LoadProgress after each table
        """
        self._progress_callback = callback
    
    def get_load_order(self) -> List[str]:
        """
        Get the table load order respecting FK dependencies.
        
        Returns:
            List of table names in proper load order
        """
        return self.integrity_handler.get_load_order()
    
    def load_from_csv_directory(
        self,
        directory: Union[str, Path],
        tables: Optional[List[str]] = None,
        resume: bool = False,
        mode: str = "initial"
    ) -> LoadSummary:
        """
        Load data from CSV files in a directory.
        
        CSV files should be named {table_name}.csv.
        
        Args:
            directory: Directory containing CSV files
            tables: Optional list of specific tables to load (loads all if None)
            resume: If True, skip tables that were already loaded successfully
            mode: Load mode ('initial' or 'incremental') for state tracking
            
        Returns:
            LoadSummary with results for all tables
        """
        directory = Path(directory)
        
        if not directory.exists():
            self._logger.error(f"Directory not found: {directory}")
            return LoadSummary(
                results=[],
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        # Find CSV files
        csv_files = {
            f.stem: f for f in directory.glob("*.csv")
        }
        
        if not csv_files:
            self._logger.warning(f"No CSV files found in {directory}")
            return LoadSummary(
                results=[],
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        # Determine tables to load
        load_order = self.get_load_order()
        
        if tables:
            # Filter to requested tables, maintain order
            tables_to_load = [t for t in load_order if t in tables and t in csv_files]
        else:
            # Load all available tables in order
            tables_to_load = [t for t in load_order if t in csv_files]
        
        # Handle resume logic
        if resume:
            self._state = LoadState.load()
            if self._state and self._state.input_dir == str(directory):
                # Filter out already successful tables
                original_count = len(tables_to_load)
                tables_to_load = [
                    t for t in tables_to_load 
                    if self._state.should_load(t)
                ]
                skipped = original_count - len(tables_to_load)
                if skipped > 0:
                    self._logger.info(
                        f"Resume mode: skipping {skipped} already loaded tables"
                    )
            else:
                # State doesn't match, start fresh
                self._state = LoadState.create_new(mode, str(directory))
        else:
            # Fresh start
            self._state = LoadState.create_new(mode, str(directory))
        
        # Initialize all tables as pending
        for table_name in tables_to_load:
            self._state.mark_pending(table_name)
        self._state.save()
        
        self._logger.info(f"Loading {len(tables_to_load)} tables from {directory}")
        
        # Initialize progress
        self._progress = LoadProgress(
            total_tables=len(tables_to_load),
            total_rows=self._count_csv_rows(csv_files, tables_to_load)
        )
        
        # Load each table
        summary = LoadSummary(started_at=datetime.now())
        
        for table_name in tables_to_load:
            csv_path = csv_files[table_name]
            self._progress.current_table = table_name
            
            self._logger.info(f"Loading {table_name} from {csv_path.name}")
            
            # Load CSV to DataFrame first to get row count
            try:
                df = pd.read_csv(csv_path)
                result = self.loader.load_dataframe(df, table_name)
            except Exception as e:
                result = LoadResult(
                    table_name=table_name,
                    rows_loaded=0,
                    success=False,
                    method=self.loader._select_load_method(0),
                    errors=[str(e)]
                )
            
            summary.results.append(result)
            
            # Update state
            if result.success:
                self._state.mark_success(table_name, result.rows_loaded)
            else:
                error_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                self._state.mark_failed(table_name, error_msg)
            self._state.save()
            
            # Update progress
            self._progress.loaded_tables += 1
            self._progress.loaded_rows += result.rows_loaded
            
            if self._progress_callback:
                self._progress_callback(self._progress)
            
            # Check for errors
            if not result.success and not self.config.continue_on_error:
                self._logger.error(f"Aborting load due to error in {table_name}")
                break
        
        # Mark completion
        self._state.completed_at = datetime.now().isoformat()
        self._state.save()
        
        summary.completed_at = datetime.now()
        self._logger.info(str(summary))
        return summary
    
    def get_last_state(self) -> Optional[LoadState]:
        """Get the last load state from file."""
        return LoadState.load()
    
    def clear_state(self) -> None:
        """Clear the saved load state."""
        LoadState.clear()
    
    def load_from_generation_result(
        self,
        result: DataGenerationResult,
        tables: Optional[List[str]] = None
    ) -> LoadSummary:
        """
        Load data from a DataGenerationResult (in-memory DataFrames).
        
        Args:
            result: DataGenerationResult from data generators
            tables: Optional list of specific tables to load
            
        Returns:
            LoadSummary with results for all tables
        """
        all_data = result.get_all_data()
        
        if not all_data:
            self._logger.warning("No data to load")
            return LoadSummary(
                results=[],
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        # Determine tables to load
        load_order = self.get_load_order()
        
        if tables:
            tables_to_load = [t for t in load_order if t in tables and t in all_data]
        else:
            tables_to_load = [t for t in load_order if t in all_data]
        
        self._logger.info(f"Loading {len(tables_to_load)} tables from generation result")
        
        # Initialize progress
        self._progress = LoadProgress(
            total_tables=len(tables_to_load),
            total_rows=sum(all_data[t].row_count for t in tables_to_load)
        )
        
        # Load each table
        summary = LoadSummary(started_at=datetime.now())
        
        for table_name in tables_to_load:
            gen_data = all_data[table_name]
            self._progress.current_table = table_name
            
            self._logger.info(f"Loading {table_name} ({gen_data.row_count} rows)")
            
            result_load = self.loader.load_dataframe(gen_data.data, table_name)
            summary.results.append(result_load)
            
            # Update progress
            self._progress.loaded_tables += 1
            self._progress.loaded_rows += result_load.rows_loaded
            
            if self._progress_callback:
                self._progress_callback(self._progress)
            
            # Check for errors
            if not result_load.success and not self.config.continue_on_error:
                self._logger.error(f"Aborting load due to error in {table_name}")
                break
        
        summary.completed_at = datetime.now()
        self._logger.info(str(summary))
        return summary
    
    def load_from_dataframes(
        self,
        dataframes: Dict[str, pd.DataFrame],
        tables: Optional[List[str]] = None
    ) -> LoadSummary:
        """
        Load data from a dictionary of DataFrames.
        
        Args:
            dataframes: Dictionary of table_name -> DataFrame
            tables: Optional list of specific tables to load
            
        Returns:
            LoadSummary with results for all tables
        """
        if not dataframes:
            self._logger.warning("No DataFrames provided")
            return LoadSummary(
                results=[],
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        # Determine tables to load
        load_order = self.get_load_order()
        
        if tables:
            tables_to_load = [t for t in load_order if t in tables and t in dataframes]
        else:
            tables_to_load = [t for t in load_order if t in dataframes]
        
        self._logger.info(f"Loading {len(tables_to_load)} DataFrames")
        
        # Initialize progress
        self._progress = LoadProgress(
            total_tables=len(tables_to_load),
            total_rows=sum(len(dataframes[t]) for t in tables_to_load)
        )
        
        # Load each table
        summary = LoadSummary(started_at=datetime.now())
        
        for table_name in tables_to_load:
            df = dataframes[table_name]
            self._progress.current_table = table_name
            
            self._logger.info(f"Loading {table_name} ({len(df)} rows)")
            
            result = self.loader.load_dataframe(df, table_name)
            summary.results.append(result)
            
            # Update progress
            self._progress.loaded_tables += 1
            self._progress.loaded_rows += result.rows_loaded
            
            if self._progress_callback:
                self._progress_callback(self._progress)
            
            # Check for errors
            if not result.success and not self.config.continue_on_error:
                self._logger.error(f"Aborting load due to error in {table_name}")
                break
        
        summary.completed_at = datetime.now()
        self._logger.info(str(summary))
        return summary
    
    def load_single_table(
        self,
        table_name: str,
        data: Union[pd.DataFrame, Path, str]
    ) -> LoadResult:
        """
        Load a single table.
        
        Args:
            table_name: Target table name
            data: DataFrame or path to CSV file
            
        Returns:
            LoadResult for the table
        """
        self._logger.info(f"Loading single table: {table_name}")
        return self.loader.load(data, table_name)
    
    def _count_csv_rows(
        self,
        csv_files: Dict[str, Path],
        tables: List[str]
    ) -> int:
        """
        Count total rows in CSV files (for progress tracking).
        
        Uses a fast line count instead of full parsing.
        """
        total = 0
        for table in tables:
            if table in csv_files:
                path = csv_files[table]
                # Quick line count (subtract 1 for header)
                with open(path, 'r') as f:
                    total += sum(1 for _ in f) - 1
        return max(0, total)
    
    def verify_load(
        self,
        expected_counts: Optional[Dict[str, int]] = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Verify loaded data by checking row counts.
        
        Args:
            expected_counts: Optional expected row counts per table
            
        Returns:
            Dictionary with actual counts and any discrepancies
        """
        results = {}
        
        for table_name in self.get_load_order():
            if not self.loader.table_exists(table_name):
                results[table_name] = {"actual": 0, "exists": False}
                continue
            
            actual_count = self.loader.get_row_count(table_name)
            result = {"actual": actual_count, "exists": True}
            
            if expected_counts and table_name in expected_counts:
                expected = expected_counts[table_name]
                result["expected"] = expected
                result["match"] = actual_count == expected
            
            results[table_name] = result
        
        return results
