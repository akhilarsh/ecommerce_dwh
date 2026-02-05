"""
Table Creation Script - Phase 3

This script:
1. Verifies connection and existing database/schema/tables status
2. Uses existing Snowflake database (must exist)
3. Uses existing schema (must exist)
4. Saves generated SQL to outputs/ directory
5. Creates all tables in proper dependency order
6. Applies primary key and foreign key constraints
7. Validates table creation
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.connectors.snowflake_connector import SnowflakeConnector
from src.sql_generator.schema_manager import SchemaManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Output directory for generated SQL
OUTPUT_DIR = project_root / "outputs" / "generated_sql"


class TableCreator:
    """Handles table creation in Snowflake."""
    
    def __init__(
        self,
        connector: SnowflakeConnector,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None
    ):
        """
        Initialize table creator.
        
        Args:
            connector: Snowflake connection instance
            database_name: Database name (default from env)
            schema_name: Schema name (default from env)
        """
        self.connector = connector
        # Force lowercase for cross-platform compatibility
        self.database_name = (database_name or os.getenv("SNOWFLAKE_DATABASE")).lower() if (database_name or os.getenv("SNOWFLAKE_DATABASE")) else None
        if not self.database_name:
            raise ValueError("SNOWFLAKE_DATABASE environment variable is required")
        self.schema_name = (schema_name or os.getenv("SNOWFLAKE_SCHEMA")).lower() if (schema_name or os.getenv("SNOWFLAKE_SCHEMA")) else None
        if not self.schema_name:
            raise ValueError("SNOWFLAKE_SCHEMA environment variable is required")
        self.schema_manager = SchemaManager()
        
        self.stats = {
            "connection_verified": False,
            "database_exists": False,
            "schema_exists": False,
            "tables_created": 0,
            "tables_failed": 0,
            "constraints_applied": 0,
            "constraints_failed": 0,
            "errors": [],
            "new_tables_created": []  # Track names of newly created tables
        }
        
        # Pre-creation status
        self.pre_creation_status = {
            "database_available": False,
            "schema_exists": False,
            "existing_tables": [],
            "tables_to_create": []
        }
    
    def _save_sql_to_file(self, sql_statements: List[str], filename: str) -> Path:
        """
        Save SQL statements to file in outputs directory.
        
        Args:
            sql_statements: List of SQL statements
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / filename
        
        content = ";\n\n".join(sql_statements)
        if content and not content.endswith(";"):
            content += ";"
        
        output_path.write_text(content)
        logger.info(f"Saved SQL to: {output_path}")
        return output_path
    
    def verify_connection(self, table_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify connection and show current status of database, schema, and tables.
        
        Args:
            table_filter: Optional table name to check only that table
        
        Returns:
            Status dictionary with current availability information
        """
        logger.info("=" * 80)
        logger.info("CONNECTION VERIFICATION & STATUS CHECK")
        logger.info("=" * 80)
        
        status = {
            "connection_ok": False,
            "database_exists": False,
            "schema_exists": False,
            "existing_tables": [],
            "missing_tables": [],
            "warehouse_active": False
        }
        
        try:
            # Test basic connection
            logger.info("Testing Snowflake connection...")
            result = self.connector.execute_query("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
            if result:
                user, role, warehouse = result[0]
                logger.info(f"  ✓ Connected as user: {user}")
                logger.info(f"  ✓ Current role: {role}")
                logger.info(f"  ✓ Current warehouse: {warehouse}")
                status["connection_ok"] = True
                status["warehouse_active"] = warehouse is not None
            
            # Check if database exists
            logger.info(f"\nChecking database: {self.database_name}")
            db_check = self.connector.execute_query(
                f"SHOW DATABASES LIKE '{self.database_name}'"
            )
            if db_check and len(db_check) > 0:
                logger.info(f"  ✓ Database '{self.database_name}' exists")
                status["database_exists"] = True
                self.pre_creation_status["database_available"] = True
            else:
                logger.warning(f"  ✗ Database '{self.database_name}' NOT FOUND")
                logger.warning(f"    Please create the database first or check the database name")
                status["database_exists"] = False
                return status
            
            # Use the database
            self.connector.execute_query(f"USE DATABASE {self.database_name}")
            
            # Check if schema exists
            logger.info(f"\nChecking schema: {self.schema_name}")
            schema_check = self.connector.execute_query(
                f"SHOW SCHEMAS LIKE '{self.schema_name}' IN DATABASE {self.database_name}"
            )
            if schema_check and len(schema_check) > 0:
                logger.info(f"  ✓ Schema '{self.schema_name}' exists")
                status["schema_exists"] = True
                self.pre_creation_status["schema_exists"] = True
            else:
                logger.warning(f"  ✗ Schema '{self.schema_name}' NOT FOUND")
                logger.warning(f"    Please create the schema first or check the schema name")
                status["schema_exists"] = False
                return status
            
            # Check existing tables (schema exists at this point)
            if status["schema_exists"]:
                logger.info(f"\nChecking existing tables in {self.database_name}.{self.schema_name}:")
                table_check = self.connector.execute_query(f"""
                    SELECT TABLE_NAME 
                    FROM {self.database_name}.INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = '{self.schema_name.upper()}'
                    ORDER BY TABLE_NAME
                """)
                
                existing_tables = [row[0].lower() for row in table_check] if table_check else []
                status["existing_tables"] = existing_tables
                self.pre_creation_status["existing_tables"] = existing_tables
                
                # Get expected tables - filter if specific table requested
                all_expected = [t.table_name for t in self.schema_manager.all_tables]
                
                if table_filter:
                    # Validate table exists in schema
                    if table_filter.lower() not in [t.lower() for t in all_expected]:
                        logger.error(f"  ✗ Table '{table_filter}' not found in schema definition")
                        logger.info(f"  Available tables: {', '.join(all_expected[:5])}...")
                        status["table_not_found"] = True
                        return status
                    expected_tables = [t for t in all_expected if t.lower() == table_filter.lower()]
                else:
                    expected_tables = all_expected
                
                for tbl_name in expected_tables:
                    if tbl_name.lower() in [t.lower() for t in existing_tables]:
                        logger.info(f"  ✓ {tbl_name} - EXISTS")
                    else:
                        logger.info(f"  ○ {tbl_name} - TO BE CREATED")
                        status["missing_tables"].append(tbl_name)
                        self.pre_creation_status["tables_to_create"].append(tbl_name)
                
                logger.info(f"\n  Summary: {len([t for t in expected_tables if t.lower() in [e.lower() for e in existing_tables]])} existing, {len(status['missing_tables'])} to create")
            
            self.stats["connection_verified"] = True
            logger.info("\n" + "=" * 80)
            
        except Exception as e:
            error_msg = f"Connection verification failed: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
        
        return status
    
    def use_database(self) -> bool:
        """
        Use existing database (database must already exist).
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Using database: {self.database_name}")
            
            # Verify database exists
            db_check = self.connector.execute_query(
                f"SHOW DATABASES LIKE '{self.database_name}'"
            )
            
            if not db_check or len(db_check) == 0:
                error_msg = f"Database '{self.database_name}' does not exist. Please create it first."
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
                return False
            
            # Use the database
            self.connector.execute_query(f"USE DATABASE {self.database_name}")
            
            logger.info(f"✓ Database '{self.database_name}' ready")
            self.stats["database_exists"] = True
            return True
            
        except Exception as e:
            error_msg = f"Failed to use database: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False
    
    def use_schema(self) -> bool:
        """
        Use existing schema (schema must already exist).
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Using schema: {self.schema_name}")
            
            # Verify schema exists
            schema_check = self.connector.execute_query(
                f"SHOW SCHEMAS LIKE '{self.schema_name}' IN DATABASE {self.database_name}"
            )
            
            if not schema_check or len(schema_check) == 0:
                error_msg = f"Schema '{self.schema_name}' does not exist. Please create it first."
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
                return False
            
            # Use the schema
            self.connector.execute_query(f"USE SCHEMA {self.schema_name}")
            
            logger.info(f"✓ Schema '{self.schema_name}' ready")
            self.stats["schema_exists"] = True
            return True
            
        except Exception as e:
            error_msg = f"Failed to use schema: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False
    
    def create_tables(self, table_filter: Optional[str] = None) -> bool:
        """
        Create tables in proper dependency order.
        
        Args:
            table_filter: Optional table name to create only that table
        
        Returns:
            True if all successful
        """
        logger.info("=" * 80)
        logger.info("CREATING TABLES")
        logger.info("=" * 80)
        
        # Get CREATE TABLE scripts (filtered if specific table requested)
        create_scripts = self.schema_manager.get_create_table_scripts(table_filter)
        
        if table_filter and not create_scripts:
            logger.error(f"Table '{table_filter}' not found in schema")
            self.stats["errors"].append(f"Table '{table_filter}' not found")
            return False
        
        logger.info(f"Total tables to create: {len(create_scripts)}")
        
        # Save SQL to file before executing
        if table_filter:
            filename = f"01_create_{table_filter.lower()}.sql"
        else:
            filename = "01_create_tables.sql"
        self._save_sql_to_file(create_scripts, filename)
        
        # Get existing tables to accurately track which are newly created
        # (CREATE TABLE IF NOT EXISTS doesn't raise an error for existing tables)
        existing_tables = self._get_existing_tables()
        if existing_tables is None:
            # Query failed - can't determine which tables exist
            # Fall back to creating all and relying on IF NOT EXISTS behavior
            logger.warning("Could not determine existing tables, will attempt to create all")
            existing_tables_lower = set()
        else:
            existing_tables_lower = {t.lower() for t in existing_tables}
        
        success = True
        skipped = 0
        for i, sql in enumerate(create_scripts, 1):
            # Extract table name from SQL
            table_name = self._extract_table_name(sql)
            
            # Check if table already exists before creating (only if we have the list)
            if existing_tables_lower and table_name.lower() in existing_tables_lower:
                logger.info(f"[{i}/{len(create_scripts)}] ⊘ Table '{table_name}' already exists, skipping")
                skipped += 1
                continue
            
            try:
                logger.info(f"[{i}/{len(create_scripts)}] Creating table: {table_name}")
                self.connector.execute_query(sql)
                self.stats["tables_created"] += 1
                self.stats["new_tables_created"].append(table_name)
                logger.info(f"✓ Table '{table_name}' created successfully")
                
            except Exception as e:
                error_str = str(e)
                # Check if table already exists (Snowflake error 002002/42710)
                if "already exists" in error_str.lower() or "42710" in error_str:
                    logger.info(f"⊘ Table '{table_name}' already exists, skipping")
                    skipped += 1
                    continue
                
                error_msg = f"Failed to create table '{table_name}': {e}"
                logger.error(f"✗ {error_msg}")
                self.stats["tables_failed"] += 1
                self.stats["errors"].append(error_msg)
                success = False
                
                # Continue with other tables even if one fails
                continue
        
        logger.info(f"\nTables: {self.stats['tables_created']} created, {skipped} already existed")
        
        return success
    
    def _get_existing_tables(self) -> Optional[List[str]]:
        """
        Get list of existing tables in the schema.
        
        Returns:
            List of existing table names (lowercase), or None if query failed
        """
        try:
            result = self.connector.execute_query(f"""
                SELECT TABLE_NAME 
                FROM {self.database_name}.INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = '{self.schema_name.upper()}'
            """)
            return [row[0].lower() for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to query existing tables: {e}")
            return None  # Return None to indicate failure, not empty list
    
    def apply_foreign_keys(self, table_filter: Optional[str] = None) -> bool:
        """
        Apply foreign key constraints to tables.
        
        Args:
            table_filter: Optional table name to apply FKs only for that table
        
        Returns:
            True if all successful
        """
        logger.info("=" * 80)
        logger.info("APPLYING FOREIGN KEY CONSTRAINTS")
        logger.info("=" * 80)
        
        # Get foreign key scripts (filtered if specific table requested)
        fk_scripts = self.schema_manager.get_foreign_key_scripts(table_filter)
        
        if not fk_scripts:
            logger.info("No foreign keys to apply for this table")
            return True
        
        logger.info(f"Total foreign keys to create: {len(fk_scripts)}")
        
        # Save FK SQL to file before executing
        if table_filter:
            filename = f"02_foreign_keys_{table_filter.lower()}.sql"
        else:
            filename = "02_foreign_keys.sql"
        self._save_sql_to_file(fk_scripts, filename)
        
        success = True
        skipped = 0
        for i, sql in enumerate(fk_scripts, 1):
            # Extract table and constraint name
            constraint_info = self._extract_constraint_info(sql)
            
            try:
                logger.info(f"[{i}/{len(fk_scripts)}] Adding FK: {constraint_info}")
                self.connector.execute_query(sql)
                self.stats["constraints_applied"] += 1
                logger.info(f"✓ Foreign key added successfully")
                
            except Exception as e:
                error_str = str(e)
                # Check if constraint already exists (Snowflake error 002002/42710)
                if "already exists" in error_str.lower() or "42710" in error_str:
                    logger.info(f"⊘ Foreign key '{constraint_info}' already exists, skipping")
                    skipped += 1
                    continue
                
                error_msg = f"Failed to add foreign key '{constraint_info}': {e}"
                logger.error(f"✗ {error_msg}")
                self.stats["constraints_failed"] += 1
                self.stats["errors"].append(error_msg)
                success = False
                
                # Continue with other constraints even if one fails
                continue
        
        logger.info(f"\nForeign keys: {self.stats['constraints_applied']} added, {skipped} already existed")
        
        return success
    
    def validate_creation(self) -> Dict[str, Any]:
        """
        Validate that all tables were created successfully.
        
        Returns:
            Validation results dictionary
        """
        logger.info("=" * 80)
        logger.info("VALIDATING TABLE CREATION")
        logger.info("=" * 80)
        
        validation = {
            "tables_found": [],
            "tables_missing": [],
            "total_expected": len(self.schema_manager.all_tables)
        }
        
        # Check each table
        for table in self.schema_manager.all_tables:
            table_name = table.table_name
            
            try:
                # Check if table exists
                sql = f"""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = '{self.schema_name.upper()}'
                    AND TABLE_NAME = '{table_name.upper()}'
                """
                result = self.connector.execute_query(sql)
                
                if result and result[0][0] > 0:
                    validation["tables_found"].append(table_name)
                    logger.info(f"✓ Table '{table_name}' exists")
                else:
                    validation["tables_missing"].append(table_name)
                    logger.warning(f"✗ Table '{table_name}' NOT FOUND")
                    
            except Exception as e:
                logger.error(f"Error checking table '{table_name}': {e}")
                validation["tables_missing"].append(table_name)
        
        validation["total_found"] = len(validation["tables_found"])
        validation["total_missing"] = len(validation["tables_missing"])
        
        logger.info(f"\nValidation Summary:")
        logger.info(f"  Expected: {validation['total_expected']} tables")
        logger.info(f"  Found: {validation['total_found']} tables")
        logger.info(f"  Missing: {validation['total_missing']} tables")
        
        return validation
    
    def get_creation_summary(self) -> Dict[str, Any]:
        """
        Get summary of table creation results.
        
        Returns:
            Summary dictionary
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "database": self.database_name,
            "schema": self.schema_name,
            "pre_creation_status": self.pre_creation_status.copy(),
            "statistics": self.stats.copy(),
            "success": (
                self.stats["database_exists"] and
                self.stats["schema_exists"] and
                self.stats["tables_failed"] == 0
            )
        }
        
        return summary
    
    def _extract_table_name(self, sql: str) -> str:
        """
        Extract table name from CREATE TABLE SQL.
        
        Args:
            sql: CREATE TABLE SQL statement
            
        Returns:
            Table name (without schema prefix)
        """
        try:
            # Handle "CREATE TABLE IF NOT EXISTS schema.table_name"
            # or "CREATE TABLE schema.table_name"
            upper_sql = sql.upper()
            
            if "IF NOT EXISTS" in upper_sql:
                # Find text after "IF NOT EXISTS"
                idx = upper_sql.find("IF NOT EXISTS") + len("IF NOT EXISTS")
                remaining = sql[idx:].strip()
                full_name = remaining.split()[0].split("(")[0].strip()
            else:
                # Find text after "CREATE TABLE"
                parts = sql.split()
                for i, part in enumerate(parts):
                    if part.upper() == "TABLE":
                        full_name = parts[i + 1].strip("(").strip()
                        break
                else:
                    return "UNKNOWN"
            
            # Return just the table name (strip schema prefix)
            if "." in full_name:
                return full_name.split(".")[-1]
            return full_name
        except:
            return "UNKNOWN"
    
    def _extract_constraint_info(self, sql: str) -> str:
        """
        Extract constraint information from ALTER TABLE SQL.
        
        Args:
            sql: ALTER TABLE SQL statement
            
        Returns:
            Constraint description
        """
        try:
            # Extract table and constraint name
            if "CONSTRAINT" in sql:
                parts = sql.split("CONSTRAINT")
                if len(parts) > 1:
                    constraint_name = parts[1].split()[0].strip()
                    return constraint_name
            return "UNKNOWN"
        except:
            return "UNKNOWN"
    
    def create_all(self, apply_fks: bool = True) -> bool:
        """
        Execute full table creation: tables and constraints.
        
        Args:
            apply_fks: Whether to apply foreign keys (default: True)
            
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("STARTING TABLE CREATION - PHASE 3")
        logger.info("=" * 80)
        logger.info(f"Database: {self.database_name}")
        logger.info(f"Schema: {self.schema_name}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        
        # Step 1: Verify connection and show current status
        connection_status = self.verify_connection()
        if not connection_status["connection_ok"]:
            logger.error("Connection verification failed. Aborting.")
            return False
        
        # Step 2: Use existing database (must exist)
        if not connection_status["database_exists"]:
            logger.error(f"Database '{self.database_name}' does not exist. Aborting.")
            logger.error("Please create the database first using: CREATE DATABASE <database_name>")
            return False
        
        if not self.use_database():
            logger.error("Failed to use database. Aborting.")
            return False
        
        # Step 3: Use existing schema (must exist)
        if not connection_status["schema_exists"]:
            logger.error(f"Schema '{self.schema_name}' does not exist. Aborting.")
            logger.error(f"Please create the schema first using: CREATE SCHEMA {self.database_name}.{self.schema_name}")
            return False
        
        if not self.use_schema():
            logger.error("Failed to use schema. Aborting.")
            return False
        
        # Step 4: Create tables
        tables_success = self.create_tables()
        
        # Step 5: Apply foreign keys (optional)
        fk_success = True
        if apply_fks:
            fk_success = self.apply_foreign_keys()
        else:
            logger.info("Skipping foreign key constraints (apply_fks=False)")
        
        # Step 6: Validate creation
        validation = self.validate_creation()
        
        # Print summary
        self._print_creation_summary(validation)
        
        # Overall success
        success = tables_success and (fk_success or not apply_fks)
        
        if success:
            logger.info("=" * 80)
            logger.info("✓ TABLE CREATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
        else:
            logger.error("=" * 80)
            logger.error("✗ TABLE CREATION COMPLETED WITH ERRORS")
            logger.error("=" * 80)
        
        return success
    
    def _print_creation_summary(self, validation: Dict) -> None:
        """Print creation summary."""
        logger.info("=" * 80)
        logger.info("CREATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Database: {self.database_name} - {'✓' if self.stats['database_exists'] else '✗'}")
        logger.info(f"Schema: {self.schema_name} - {'✓' if self.stats['schema_exists'] else '✗'}")
        logger.info(f"Tables Created: {self.stats['tables_created']}")
        logger.info(f"Tables Failed: {self.stats['tables_failed']}")
        logger.info(f"Foreign Keys Applied: {self.stats['constraints_applied']}")
        logger.info(f"Foreign Keys Failed: {self.stats['constraints_failed']}")
        logger.info(f"Tables Validated: {validation['total_found']}/{validation['total_expected']}")
        
        if self.stats['errors']:
            logger.info(f"\nErrors encountered: {len(self.stats['errors'])}")
            for i, error in enumerate(self.stats['errors'][:5], 1):  # Show first 5 errors
                logger.error(f"  {i}. {error}")
            if len(self.stats['errors']) > 5:
                logger.error(f"  ... and {len(self.stats['errors']) - 5} more errors")


def main():
    """Main execution function."""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        logger.info("Initializing table creation...")
        
        # Create connector
        logger.info("Creating Snowflake connection...")
        connector = SnowflakeConnector()
        
        # Create tables
        with connector:
            creator = TableCreator(connector)
            success = creator.create_all(apply_fks=True)
            
            # Get summary
            summary = creator.get_creation_summary()
            
            if success:
                logger.info("\n" + "=" * 80)
                logger.info("Phase 3: Table Creation - COMPLETE ✓")
                logger.info("=" * 80)
                return 0
            else:
                logger.error("\n" + "=" * 80)
                logger.error("Phase 3: Table Creation - FAILED ✗")
                logger.error("=" * 80)
                return 1
                
    except Exception as e:
        logger.error(f"Fatal error during table creation: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
