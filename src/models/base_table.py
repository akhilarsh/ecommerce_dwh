"""
Base table abstract class and column definitions.

Provides foundation for programmatic table definition.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Column:
    """Represents a database column definition."""
    
    name: str
    data_type: str
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    nullable: bool = True
    default: Optional[str] = None
    comment: Optional[str] = None
    
    def to_sql(self) -> str:
        """
        Generate SQL column definition.
        
        Returns:
            SQL column definition string
        """
        sql_parts = [self.name, self.data_type]
        
        # Add length for VARCHAR
        if self.data_type.upper() == "VARCHAR" and self.length:
            sql_parts[1] = f"VARCHAR({self.length})"
        
        # Add precision/scale for NUMBER
        elif self.data_type.upper() == "NUMBER":
            if self.precision and self.scale is not None:
                sql_parts[1] = f"NUMBER({self.precision},{self.scale})"
            elif self.precision:
                sql_parts[1] = f"NUMBER({self.precision})"
        
        # Nullable constraint
        if not self.nullable:
            sql_parts.append("NOT NULL")
        
        # Default value
        if self.default:
            sql_parts.append(f"DEFAULT {self.default}")
        
        # Comment
        if self.comment:
            sql_parts.append(f"COMMENT '{self.comment}'")
        
        return " ".join(sql_parts)


@dataclass
class ForeignKey:
    """Represents a foreign key constraint."""
    
    column: str
    reference_table: str
    reference_column: str
    on_delete: str = "RESTRICT"
    on_update: str = "RESTRICT"
    constraint_name: Optional[str] = None
    
    def to_sql(self, table_name: str, qualified_prefix: str) -> str:
        """
        Generate SQL foreign key constraint.
        
        Args:
            table_name: Fully qualified name of the table containing this FK
            qualified_prefix: The database.schema prefix for reference tables
            
        Returns:
            SQL ALTER TABLE statement for FK
        """
        # Use just the table name part for constraint naming
        base_table = table_name.split('.')[-1]
        if not self.constraint_name:
            self.constraint_name = f"fk_{base_table}_{self.column}"
        
        # Build fully qualified reference table name (lowercase)
        ref_table = f"{qualified_prefix}.{self.reference_table.lower()}"
        
        sql = (
            f"ALTER TABLE {table_name} "
            f"ADD CONSTRAINT {self.constraint_name} "
            f"FOREIGN KEY ({self.column}) "
            f"REFERENCES {ref_table}({self.reference_column})"
        )
        
        if self.on_delete != "RESTRICT":
            sql += f" ON DELETE {self.on_delete}"
        
        if self.on_update != "RESTRICT":
            sql += f" ON UPDATE {self.on_update}"
        
        sql += ";"
        
        return sql


class BaseTable(ABC):
    """
    Abstract base class for table definitions.
    
    All table models should inherit from this class and implement:
    - define_columns(): List of Column objects
    - table_name: str
    """
    
    table_name: str = ""
    primary_key: List[str] = []
    foreign_keys: List[ForeignKey] = []
    cluster_keys: List[str] = []
    comment: Optional[str] = None
    
    @abstractmethod
    def define_columns(self) -> List[Column]:
        """
        Define table columns.
        
        Returns:
            List of Column objects
        """
        pass
    
    @classmethod
    def get_qualified_prefix(cls) -> str:
        """
        Get database.schema prefix from environment based on DWH platform.
        
        Returns:
            Fully qualified prefix (database.schema)
            
        Raises:
            ValueError: If required environment variables are not set
        """
        platform = os.getenv("DWH_PLATFORM")
        if not platform:
            raise ValueError("DWH_PLATFORM environment variable is required")
        
        platform = platform.lower()
        
        if platform in ("sf", "snowflake"):
            database = os.getenv("SNOWFLAKE_DATABASE")
            schema = os.getenv("SNOWFLAKE_SCHEMA")
            if not database or not schema:
                raise ValueError("SNOWFLAKE_DATABASE and SNOWFLAKE_SCHEMA are required")
        elif platform in ("bq", "bigquery"):
            database = os.getenv("BIGQUERY_PROJECT")
            schema = os.getenv("BIGQUERY_DATASET")
            if not database or not schema:
                raise ValueError("BIGQUERY_PROJECT and BIGQUERY_DATASET are required")
        elif platform in ("rs", "redshift"):
            database = os.getenv("REDSHIFT_DATABASE")
            schema = os.getenv("REDSHIFT_SCHEMA")
            if not database or not schema:
                raise ValueError("REDSHIFT_DATABASE and REDSHIFT_SCHEMA are required")
        elif platform in ("db", "databricks"):
            database = os.getenv("DATABRICKS_CATALOG")
            schema = os.getenv("DATABRICKS_SCHEMA")
            if not database or not schema:
                raise ValueError("DATABRICKS_CATALOG and DATABRICKS_SCHEMA are required")
        else:
            raise ValueError(f"Unsupported DWH platform: {platform}")
        
        # Force lowercase for cross-platform compatibility
        return f"{database.lower()}.{schema.lower()}"
    
    def get_full_table_name(self) -> str:
        """
        Get fully qualified table name (database.schema.table).
        
        Returns:
            Fully qualified table name
        """
        return f"{self.get_qualified_prefix()}.{self.table_name.lower()}"
    
    def get_create_table_sql(self) -> str:
        """
        Generate CREATE TABLE SQL statement.
        
        Returns:
            Complete CREATE TABLE SQL
        """
        if not self.table_name:
            raise ValueError("table_name must be defined")
        
        columns = self.define_columns()
        if not columns:
            raise ValueError(f"No columns defined for {self.table_name}")
        
        # Build column definitions
        column_defs = [f"  {col.to_sql()}" for col in columns]
        
        # Add primary key if defined
        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            column_defs.append(f"  PRIMARY KEY ({pk_cols})")
        
        columns_sql = ",\n".join(column_defs)
        
        # Build CREATE TABLE statement
        sql = f"CREATE TABLE IF NOT EXISTS {self.get_full_table_name()} (\n{columns_sql}\n)"
        
        # Add table comment
        if self.comment:
            sql += f"\nCOMMENT = '{self.comment}'"
        
        # Add clustering keys
        if self.cluster_keys:
            cluster_cols = ", ".join(self.cluster_keys)
            sql += f"\nCLUSTER BY ({cluster_cols})"
        
        # Add statement terminator
        sql += ";"
        
        return sql
    
    def get_foreign_key_sql(self) -> List[str]:
        """
        Generate ALTER TABLE statements for foreign keys.
        
        Returns:
            List of ALTER TABLE SQL statements
        """
        prefix = self.get_qualified_prefix()
        return [fk.to_sql(self.get_full_table_name(), prefix) for fk in self.foreign_keys]
    
    def validate(self) -> bool:
        """
        Validate table definition.
        
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        if not self.table_name:
            raise ValueError("table_name is required")
        
        columns = self.define_columns()
        if not columns:
            raise ValueError(f"No columns defined for {self.table_name}")
        
        # Validate primary key columns exist
        if self.primary_key:
            column_names = [col.name for col in columns]
            for pk_col in self.primary_key:
                if pk_col not in column_names:
                    raise ValueError(
                        f"Primary key column '{pk_col}' not found in table columns"
                    )
        
        # Validate foreign key columns exist
        if self.foreign_keys:
            column_names = [col.name for col in columns]
            for fk in self.foreign_keys:
                if fk.column not in column_names:
                    raise ValueError(
                        f"Foreign key column '{fk.column}' not found in table columns"
                    )
        
        return True
