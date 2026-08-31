"""
Base helper class for domain helpers.

Provides shared functionality for all domain helpers including:
- Configuration access
- Faker instance management
- Volume checking utilities
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from faker import Faker

from ..config import DataGenConfig
from ..utils.keys_loader import ExistingKeysLoader
from ...utils.logger import get_logger


@dataclass
class GeneratedData:
    """Container for generated data."""
    
    table_name: str
    data: pd.DataFrame
    surrogate_keys: List[int] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def row_count(self) -> int:
        """Get number of rows."""
        return len(self.data) if self.data is not None else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "table_name": self.table_name,
            "row_count": self.row_count,
            "columns": list(self.data.columns) if self.data is not None else [],
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DataGenerationResult:
    """Result container for complete data generation."""
    
    dimensions: Dict[str, GeneratedData] = field(default_factory=dict)
    facts: Dict[str, GeneratedData] = field(default_factory=dict)
    keys: Dict[str, List[int]] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def total_records(self) -> int:
        """Calculate total records."""
        return sum(d.row_count for d in self.dimensions.values()) + \
               sum(f.row_count for f in self.facts.values())
    
    @staticmethod
    def _combine(existing: GeneratedData, new: GeneratedData) -> GeneratedData:
        """Concatenate a new chunk onto data already added for the same table."""
        frames = [
            df for df in (existing.data, new.data)
            if df is not None and not df.empty
        ]
        if not frames:
            combined = existing.data if existing.data is not None else new.data
        elif len(frames) == 1:
            combined = frames[0]
        else:
            combined = pd.concat(frames, ignore_index=True)

        return GeneratedData(
            table_name=existing.table_name,
            data=combined,
            surrogate_keys=[*existing.surrogate_keys, *new.surrogate_keys],
            generated_at=existing.generated_at,
        )

    def add_dimension(self, data: GeneratedData) -> None:
        """Add dimension data to result, concatenating repeated chunks."""
        existing = self.dimensions.get(data.table_name)
        merged = self._combine(existing, data) if existing else data
        self.dimensions[merged.table_name] = merged
        if merged.surrogate_keys:
            self.keys[merged.table_name] = merged.surrogate_keys
    
    def add_fact(self, data: GeneratedData) -> None:
        """Add fact data to result, concatenating repeated chunks."""
        existing = self.facts.get(data.table_name)
        merged = self._combine(existing, data) if existing else data
        self.facts[merged.table_name] = merged
        if merged.surrogate_keys:
            self.keys[merged.table_name] = merged.surrogate_keys
    
    def merge(self, other: "DataGenerationResult") -> None:
        """Merge another result into this one."""
        self.dimensions.update(other.dimensions)
        self.facts.update(other.facts)
        self.keys.update(other.keys)
    
    def get_all_data(self) -> Dict[str, GeneratedData]:
        """Get all generated data as single dictionary."""
        return {**self.dimensions, **self.facts}
    
    def get_table_data(self, table_name: str) -> Optional[GeneratedData]:
        """Get data for specific table."""
        return self.dimensions.get(table_name) or self.facts.get(table_name)
    
    def get_dataframe(self, table_name: str) -> Optional[pd.DataFrame]:
        """Get DataFrame for specific table."""
        data = self.get_table_data(table_name)
        return data.data if data else None
    
    def summary(self) -> Dict[str, Any]:
        """Get summary of generated data."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_records": self.total_records,
            "dimension_tables": {
                name: data.row_count for name, data in self.dimensions.items()
            },
            "fact_tables": {
                name: data.row_count for name, data in self.facts.items()
            },
        }


class BaseHelper(ABC):
    """
    Base class for domain helpers.
    
    Provides shared functionality including:
    - Configuration access
    - Faker instance with seeding
    - Volume checking utilities
    - Logging
    """
    
    def __init__(self, config: DataGenConfig, keys_loader: ExistingKeysLoader):
        """
        Initialize the helper.
        
        Args:
            config: Data generation configuration
            keys_loader: Existing keys loader for referential integrity
        """
        self.config = config
        self.keys_loader = keys_loader
        self.logger = get_logger(f"generator.helper.{self.name}")
        
        # Initialize Faker with seed and locale
        self.faker = Faker(self.config.settings.locale)
        if self.config.settings.seed is not None:
            Faker.seed(self.config.settings.seed)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Helper name for logging."""
        pass
    
    @abstractmethod
    def generate(self) -> DataGenerationResult:
        """
        Generate all entities this helper manages (based on config volumes).
        
        Returns:
            DataGenerationResult containing all generated data
        """
        pass
    
    def _should_generate(self, volume_key: str) -> bool:
        """
        Check if entity should be generated based on config.
        
        Args:
            volume_key: Attribute name in config.volumes
            
        Returns:
            True if volume > 0, False otherwise
        """
        volume = getattr(self.config.volumes, volume_key, 0)
        return volume is not None and volume > 0
    
    def _get_volume(self, volume_key: str) -> int:
        """
        Get volume from config, default 0.
        
        Args:
            volume_key: Attribute name in config.volumes
            
        Returns:
            Volume value or 0 if not set
        """
        return getattr(self.config.volumes, volume_key, 0) or 0
    
    def _create_dataframe(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Create DataFrame from list of records.
        
        Args:
            records: List of dictionaries representing rows
            
        Returns:
            pandas DataFrame
        """
        return pd.DataFrame(records) if records else pd.DataFrame()
    
    def _get_dimension_keys(self, table_name: str) -> List[int]:
        """
        Get valid keys for a dimension table.
        
        Args:
            table_name: Name of the dimension table
            
        Returns:
            List of valid surrogate keys
        """
        return self.keys_loader.get_valid_fk_keys(table_name)
    
    def _get_next_key(self, table_name: str) -> int:
        """
        Get next available surrogate key for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Next surrogate key value
        """
        return self.keys_loader.get_next_key(table_name)
    
    def _update_keys(self, table_name: str, keys: List[int]) -> None:
        """
        Update keys cache after generation.
        
        Args:
            table_name: Name of the table
            keys: List of generated keys
        """
        self.keys_loader.update_after_generation(table_name, keys)
