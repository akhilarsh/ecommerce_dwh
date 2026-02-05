"""
Base connector interface for data warehouse connections.

All DWH connectors must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseConnector(ABC):
    """
    Abstract base class for data warehouse connectors.
    
    All DWH-specific connectors (Snowflake, BigQuery, Redshift, Databricks)
    must implement this interface to ensure consistent behavior across platforms.
    """
    
    # Platform identifier (set by subclasses)
    PLATFORM: str = "base"
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the data warehouse."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the data warehouse connection."""
        pass
    
    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """
        Execute SQL query and return results as tuples.
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            List of result tuples
        """
        pass
    
    @abstractmethod
    def execute_dict(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        pass
    
    @abstractmethod
    def execute_many(
        self,
        query: str,
        data: List[tuple]
    ) -> None:
        """
        Execute query with multiple parameter sets (batch insert).
        
        Args:
            query: SQL query with placeholders
            data: List of parameter tuples
        """
        pass
    
    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction."""
        pass
    
    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction."""
        pass
    
    @abstractmethod
    def get_current_database(self) -> Optional[str]:
        """Get current database name."""
        pass
    
    @abstractmethod
    def get_current_schema(self) -> Optional[str]:
        """Get current schema name."""
        pass
    
    @abstractmethod
    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        """
        Check if table exists.
        
        Args:
            table_name: Name of table
            schema: Schema name (uses current if not provided)
            
        Returns:
            True if table exists
        """
        pass
    
    @abstractmethod
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get current connection information.
        
        Returns:
            Dictionary with connection details (user, database, schema, etc.)
        """
        pass
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - rollback on error, close connection."""
        if exc_type:
            self.rollback()
        self.close()
        return False
