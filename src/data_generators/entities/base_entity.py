"""
Base entity generator class.

Provides common functionality for all entity generators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from faker import Faker

from ..config import DataGenConfig
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


class BaseEntityGenerator(ABC):
    """
    Base class for entity generators.
    
    Each entity generator is responsible for creating synthetic data
    for a single table in the data warehouse.
    """
    
    def __init__(self, config: DataGenConfig):
        """
        Initialize the generator.
        
        Args:
            config: Data generation configuration
        """
        self.config = config
        self.logger = get_logger(f"generator.entity.{self.table_name}")
        
        # Initialize Faker
        self.faker = Faker(self.config.settings.locale)
        if self.config.settings.seed is not None:
            Faker.seed(self.config.settings.seed)
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Table name this generator creates data for."""
        pass
    
    @abstractmethod
    def generate(self, count: int, start_key: int = 1, **kwargs) -> GeneratedData:
        """
        Generate records for this entity.
        
        Args:
            count: Number of records to generate
            start_key: Starting surrogate key value
            **kwargs: Additional parameters (dimension keys, etc.)
            
        Returns:
            GeneratedData container with DataFrame and keys
        """
        pass
    
    def _create_dataframe(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Create DataFrame from records."""
        return pd.DataFrame(records) if records else pd.DataFrame()
    
    def _generate_keys(self, count: int, start_key: int) -> List[int]:
        """Generate surrogate keys."""
        return list(range(start_key, start_key + count))
