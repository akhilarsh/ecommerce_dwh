"""
DDL Generator Module.

Generates CREATE TABLE SQL statements from table models.
"""

import sys
from pathlib import Path
from typing import List, Type

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models.base_table import BaseTable
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DDLGenerator:
    """Generates DDL (Data Definition Language) SQL statements."""
    
    def __init__(self):
        """Initialize DDL generator."""
        self.generated_tables: List[str] = []
    
    def generate_create_table(self, table: BaseTable) -> str:
        """
        Generate CREATE TABLE SQL statement for a table.
        
        Args:
            table: Table model instance
            
        Returns:
            CREATE TABLE SQL statement
        """
        try:
            logger.info(f"Generating CREATE TABLE for {table.get_full_table_name()}")
            
            # Validate table before generating SQL
            table.validate()
            
            # Generate the CREATE TABLE SQL
            sql = table.get_create_table_sql()
            
            self.generated_tables.append(table.table_name)
            logger.debug(f"Generated SQL:\n{sql}")
            
            return sql
            
        except Exception as e:
            logger.error(f"Failed to generate CREATE TABLE for {table.table_name}: {e}")
            raise
    
    def generate_create_tables(self, tables: List[BaseTable]) -> List[str]:
        """
        Generate CREATE TABLE SQL statements for multiple tables.
        
        Args:
            tables: List of table model instances
            
        Returns:
            List of CREATE TABLE SQL statements
        """
        sql_statements = []
        
        for table in tables:
            try:
                sql = self.generate_create_table(table)
                sql_statements.append(sql)
            except Exception as e:
                logger.error(f"Skipping table {table.table_name} due to error: {e}")
                continue
        
        logger.info(f"Generated {len(sql_statements)} CREATE TABLE statements")
        return sql_statements
    
    def generate_drop_table(self, table: BaseTable, if_exists: bool = True) -> str:
        """
        Generate DROP TABLE SQL statement.
        
        Args:
            table: Table model instance
            if_exists: Include IF EXISTS clause
            
        Returns:
            DROP TABLE SQL statement
        """
        full_table_name = table.get_full_table_name()
        
        if if_exists:
            sql = f"DROP TABLE IF EXISTS {full_table_name};"
        else:
            sql = f"DROP TABLE {full_table_name};"
        
        logger.debug(f"Generated DROP TABLE: {sql}")
        return sql
    
    def generate_drop_tables(self, tables: List[BaseTable], if_exists: bool = True) -> List[str]:
        """
        Generate DROP TABLE SQL statements for multiple tables.
        
        Args:
            tables: List of table model instances
            if_exists: Include IF EXISTS clause
            
        Returns:
            List of DROP TABLE SQL statements
        """
        sql_statements = []
        
        # Drop in reverse order to handle dependencies
        for table in reversed(tables):
            sql = self.generate_drop_table(table, if_exists)
            sql_statements.append(sql)
        
        logger.info(f"Generated {len(sql_statements)} DROP TABLE statements")
        return sql_statements
    
    def save_to_file(self, sql_statements: List[str], filepath: str):
        """
        Save SQL statements to a file.
        
        Args:
            sql_statements: List of SQL statements
            filepath: Output file path
        """
        try:
            with open(filepath, 'w') as f:
                for sql in sql_statements:
                    # SQL already has semicolon from get_create_table_sql()
                    f.write(sql + "\n\n")
            
            logger.info(f"Saved {len(sql_statements)} SQL statements to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save SQL to {filepath}: {e}")
            raise
