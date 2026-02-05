"""
Abstract base class for data loaders.

Provides a platform-agnostic interface for loading data into various
data warehouses (Snowflake, Redshift, BigQuery, Databricks, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default state file location
DEFAULT_STATE_FILE = "outputs/.load_state.json"


class LoadMethod(Enum):
    """Data loading method."""
    
    DATAFRAME = "dataframe"  # Direct DataFrame load (write_pandas, etc.)
    STAGED = "staged"  # Staged file load (COPY INTO, etc.)
    BATCH_INSERT = "batch_insert"  # Batch INSERT statements


@dataclass
class LoadResult:
    """Result of a data load operation."""
    
    table_name: str
    rows_loaded: int
    success: bool
    method: LoadMethod
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def has_errors(self) -> bool:
        """Check if load had errors."""
        return len(self.errors) > 0
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"{self.table_name}: {status} ({self.rows_loaded} rows in {self.duration_seconds:.2f}s)"


@dataclass
class LoaderConfig:
    """Configuration for data loaders."""
    
    # Batch settings
    batch_size: int = 10000
    
    # Table handling
    truncate_before_load: bool = False
    validate_after_load: bool = True
    
    # Method selection threshold
    staged_load_threshold: int = 100000  # Use staged load for >= this many rows
    
    # Error handling
    continue_on_error: bool = False
    max_errors: int = 10
    
    # Connection settings
    database: Optional[str] = None
    schema: Optional[str] = None
    
    # Staging settings (for COPY INTO)
    stage_name: Optional[str] = None
    file_format: str = "CSV"
    
    def __post_init__(self):
        """Validate configuration."""
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.staged_load_threshold < 1:
            raise ValueError("staged_load_threshold must be at least 1")


@dataclass
class LoadSummary:
    """Summary of a multi-table load operation."""
    
    results: List[LoadResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def total_rows(self) -> int:
        """Total rows loaded across all tables."""
        return sum(r.rows_loaded for r in self.results)
    
    @property
    def total_tables(self) -> int:
        """Number of tables processed."""
        return len(self.results)
    
    @property
    def successful_tables(self) -> int:
        """Number of tables loaded successfully."""
        return sum(1 for r in self.results if r.success)
    
    @property
    def failed_tables(self) -> int:
        """Number of tables that failed to load."""
        return sum(1 for r in self.results if not r.success)
    
    @property
    def total_duration(self) -> float:
        """Total duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return sum(r.duration_seconds for r in self.results)
    
    @property
    def all_successful(self) -> bool:
        """Check if all tables loaded successfully."""
        return all(r.success for r in self.results)
    
    def get_failed_results(self) -> List[LoadResult]:
        """Get results for failed tables."""
        return [r for r in self.results if not r.success]
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.all_successful else "PARTIAL"
        return (
            f"Load {status}: {self.successful_tables}/{self.total_tables} tables, "
            f"{self.total_rows:,} rows in {self.total_duration:.2f}s"
        )


class BaseDataLoader(ABC):
    """
    Abstract base class for data warehouse loaders.
    
    Implementations should be created for each target platform:
    - SnowflakeLoader
    - RedshiftLoader (future)
    - BigQueryLoader (future)
    - DatabricksLoader (future)
    
    Usage:
        loader = SnowflakeLoader(connector, config)
        result = loader.load_dataframe(df, "dim_customers")
    """
    
    def __init__(self, config: Optional[LoaderConfig] = None):
        """
        Initialize data loader.
        
        Args:
            config: Loader configuration
        """
        self.config = config or LoaderConfig()
        self._logger = get_logger(f"loader.{self.__class__.__name__.lower()}")
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'snowflake', 'redshift')."""
        pass
    
    @abstractmethod
    def load_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        **kwargs
    ) -> LoadResult:
        """
        Load a pandas DataFrame into a table.
        
        Args:
            df: DataFrame to load
            table_name: Target table name
            **kwargs: Platform-specific options
            
        Returns:
            LoadResult with operation details
        """
        pass
    
    @abstractmethod
    def load_csv(
        self,
        filepath: Path,
        table_name: str,
        **kwargs
    ) -> LoadResult:
        """
        Load data from a CSV file into a table.
        
        Args:
            filepath: Path to CSV file
            table_name: Target table name
            **kwargs: Platform-specific options
            
        Returns:
            LoadResult with operation details
        """
        pass
    
    @abstractmethod
    def truncate_table(self, table_name: str) -> None:
        """
        Truncate (delete all rows from) a table.
        
        Args:
            table_name: Table to truncate
        """
        pass
    
    @abstractmethod
    def get_row_count(self, table_name: str) -> int:
        """
        Get the current row count of a table.
        
        Args:
            table_name: Table name
            
        Returns:
            Number of rows in the table
        """
        pass
    
    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Table name to check
            
        Returns:
            True if table exists
        """
        pass
    
    def load(
        self,
        data: pd.DataFrame | Path | str,
        table_name: str,
        **kwargs
    ) -> LoadResult:
        """
        Load data from DataFrame or file path.
        
        Automatically selects the appropriate load method based on input type.
        
        Args:
            data: DataFrame or path to CSV file
            table_name: Target table name
            **kwargs: Additional options
            
        Returns:
            LoadResult with operation details
        """
        if isinstance(data, pd.DataFrame):
            return self.load_dataframe(data, table_name, **kwargs)
        elif isinstance(data, (Path, str)):
            filepath = Path(data)
            if not filepath.exists():
                return LoadResult(
                    table_name=table_name,
                    rows_loaded=0,
                    success=False,
                    method=LoadMethod.STAGED,
                    errors=[f"File not found: {filepath}"]
                )
            return self.load_csv(filepath, table_name, **kwargs)
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")
    
    def _select_load_method(self, row_count: int) -> LoadMethod:
        """
        Select the appropriate load method based on row count.
        
        Args:
            row_count: Number of rows to load
            
        Returns:
            Recommended LoadMethod
        """
        if row_count >= self.config.staged_load_threshold:
            return LoadMethod.STAGED
        return LoadMethod.DATAFRAME
    
    def _validate_dataframe(self, df: pd.DataFrame, table_name: str) -> List[str]:
        """
        Validate a DataFrame before loading.
        
        Args:
            df: DataFrame to validate
            table_name: Target table name
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if df.empty:
            errors.append(f"DataFrame for {table_name} is empty")
        
        # Check for completely null columns
        null_cols = [col for col in df.columns if df[col].isna().all()]
        if null_cols:
            self._logger.warning(f"{table_name}: Columns are all null: {null_cols}")
        
        return errors


@dataclass
class TableLoadState:
    """State of a single table's load operation."""
    
    table_name: str
    status: str  # "success", "failed", "pending", "skipped"
    rows_loaded: int = 0
    error_message: Optional[str] = None
    loaded_at: Optional[str] = None  # ISO format timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "table_name": self.table_name,
            "status": self.status,
            "rows_loaded": self.rows_loaded,
            "error_message": self.error_message,
            "loaded_at": self.loaded_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TableLoadState":
        """Create from dictionary."""
        return cls(
            table_name=data["table_name"],
            status=data["status"],
            rows_loaded=data.get("rows_loaded", 0),
            error_message=data.get("error_message"),
            loaded_at=data.get("loaded_at"),
        )


@dataclass
class LoadState:
    """
    Persistent state for data loading operations.
    
    Tracks which tables have been loaded successfully, failed, or are pending.
    Enables resume functionality after partial failures.
    """
    
    mode: str  # "initial" or "incremental"
    input_dir: str
    started_at: str  # ISO format
    completed_at: Optional[str] = None
    tables: Dict[str, TableLoadState] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if all tables have been processed."""
        return all(
            t.status in ("success", "skipped") 
            for t in self.tables.values()
        )
    
    @property
    def failed_tables(self) -> List[str]:
        """Get list of failed table names."""
        return [
            name for name, state in self.tables.items() 
            if state.status == "failed"
        ]
    
    @property
    def successful_tables(self) -> List[str]:
        """Get list of successfully loaded table names."""
        return [
            name for name, state in self.tables.items() 
            if state.status == "success"
        ]
    
    @property
    def pending_tables(self) -> List[str]:
        """Get list of pending table names."""
        return [
            name for name, state in self.tables.items() 
            if state.status == "pending"
        ]
    
    def mark_success(self, table_name: str, rows_loaded: int) -> None:
        """Mark a table as successfully loaded."""
        self.tables[table_name] = TableLoadState(
            table_name=table_name,
            status="success",
            rows_loaded=rows_loaded,
            loaded_at=datetime.now().isoformat(),
        )
    
    def mark_failed(self, table_name: str, error: str) -> None:
        """Mark a table as failed."""
        self.tables[table_name] = TableLoadState(
            table_name=table_name,
            status="failed",
            error_message=error,
            loaded_at=datetime.now().isoformat(),
        )
    
    def mark_pending(self, table_name: str) -> None:
        """Mark a table as pending."""
        if table_name not in self.tables:
            self.tables[table_name] = TableLoadState(
                table_name=table_name,
                status="pending",
            )
    
    def mark_skipped(self, table_name: str, reason: str = "already loaded") -> None:
        """Mark a table as skipped."""
        self.tables[table_name] = TableLoadState(
            table_name=table_name,
            status="skipped",
            error_message=reason,
        )
    
    def should_load(self, table_name: str) -> bool:
        """Check if a table should be loaded (not already successful)."""
        if table_name not in self.tables:
            return True
        return self.tables[table_name].status not in ("success", "skipped")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "mode": self.mode,
            "input_dir": self.input_dir,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tables": {
                name: state.to_dict() 
                for name, state in self.tables.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoadState":
        """Create from dictionary."""
        state = cls(
            mode=data["mode"],
            input_dir=data["input_dir"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
        )
        for name, table_data in data.get("tables", {}).items():
            state.tables[name] = TableLoadState.from_dict(table_data)
        return state
    
    def save(self, filepath: Optional[Path] = None) -> None:
        """
        Save state to JSON file.
        
        Args:
            filepath: Path to save to (uses default if None)
        """
        filepath = filepath or Path(DEFAULT_STATE_FILE)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.debug(f"Saved load state to {filepath}")
    
    @classmethod
    def load(cls, filepath: Optional[Path] = None) -> Optional["LoadState"]:
        """
        Load state from JSON file.
        
        Args:
            filepath: Path to load from (uses default if None)
            
        Returns:
            LoadState if file exists, None otherwise
        """
        filepath = filepath or Path(DEFAULT_STATE_FILE)
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load state file: {e}")
            return None
    
    @classmethod
    def create_new(cls, mode: str, input_dir: str) -> "LoadState":
        """Create a new load state."""
        return cls(
            mode=mode,
            input_dir=input_dir,
            started_at=datetime.now().isoformat(),
        )
    
    @staticmethod
    def clear(filepath: Optional[Path] = None) -> None:
        """Delete the state file."""
        filepath = filepath or Path(DEFAULT_STATE_FILE)
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Cleared load state file: {filepath}")
