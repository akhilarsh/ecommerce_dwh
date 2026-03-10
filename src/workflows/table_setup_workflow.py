"""
Table Setup Workflow.

One-time workflow that creates all tables in the data warehouse
with proper foreign key dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.connectors import get_connector
from src.cli.config import get_dwh_platform
from src.table_manager.create_tables import TableCreator
from src.sql_generator.schema_manager import SchemaManager
from src.utils.logger import get_logger
from src.workflows.base_workflow import BaseWorkflow, WorkflowResult

logger = get_logger(__name__)


@dataclass
class TableSetupConfig:
    """Configuration for table setup workflow."""
    
    database: Optional[str] = None  # Uses env var if not provided
    schema: Optional[str] = None    # Uses env var if not provided
    drop_existing: bool = False     # Drop existing tables before creation
    dry_run: bool = False           # Show what would be done without executing
    apply_foreign_keys: bool = True # Apply FK constraints after table creation


class TableSetupWorkflow(BaseWorkflow):
    """
    Workflow for creating the data warehouse tables.
    
    This workflow:
    1. Validates Snowflake connection
    2. Verifies database and schema exist
    3. Optionally drops existing tables
    4. Creates all tables in FK dependency order
    5. Applies foreign key constraints
    6. Validates the creation
    
    Usage:
        # Database and schema are read from environment variables:
        # SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
        config = TableSetupConfig(
            drop_existing=False
        )
        
        workflow = TableSetupWorkflow()
        result = workflow.run(config)
        
        if result.success:
            print(f"Created {result.details['tables_created']} tables")
    """
    
    @property
    def name(self) -> str:
        return "table_setup"
    
    @property
    def description(self) -> str:
        return "Create all data warehouse tables with FK constraints"
    
    def run(self, config: Optional[TableSetupConfig] = None) -> WorkflowResult:
        """
        Execute the table setup workflow.
        
        Args:
            config: Workflow configuration (uses defaults if not provided)
            
        Returns:
            WorkflowResult with execution details
        """
        config = config or TableSetupConfig()
        started_at = datetime.now()
        stages_completed: List[str] = []
        details: Dict[str, Any] = {
            "database": config.database,
            "schema": config.schema,
            "dry_run": config.dry_run,
            "drop_existing": config.drop_existing
        }
        
        self._log_start()
        logger.info(f"Configuration:")
        logger.info(f"  Database: {config.database or '(from env)'}")
        logger.info(f"  Schema: {config.schema or '(from env)'}")
        logger.info(f"  Drop existing: {config.drop_existing}")
        logger.info(f"  Dry run: {config.dry_run}")
        logger.info(f"  Apply FKs: {config.apply_foreign_keys}")
        
        if config.dry_run:
            return self._execute_dry_run(config, started_at)
        
        try:
            # Stage 1: Connect to DWH
            platform = get_dwh_platform()
            logger.info(f"\n[1/6] Connecting to {platform}...")
            connector = get_connector(platform)
            
            with connector:
                stages_completed.append("connect")
                
                # Stage 2: Verify database and schema
                logger.info("\n[2/6] Verifying database and schema...")
                creator = TableCreator(
                    connector,
                    database_name=config.database,
                    schema_name=config.schema
                )
                
                status = creator.verify_connection()
                details["database"] = creator.database_name
                details["schema"] = creator.schema_name
                
                if not status["connection_ok"]:
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error="Connection verification failed",
                        details=details
                    )
                
                if not status["database_exists"]:
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error=f"Database '{creator.database_name}' does not exist",
                        details=details
                    )
                
                if not status["schema_exists"]:
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error=f"Schema '{creator.schema_name}' does not exist",
                        details=details
                    )
                
                stages_completed.append("verify_db_schema")
                existing_tables = status.get("existing_tables", [])
                details["existing_tables"] = existing_tables
                
                # Stage 3: Drop existing tables if requested
                if config.drop_existing:
                    logger.info("\n[3/6] Dropping existing tables...")
                    self._drop_existing_tables(creator, existing_tables)
                    stages_completed.append("drop_existing")
                else:
                    logger.info("\n[3/6] Skipping drop (drop_existing=False)")
                    stages_completed.append("skip_drop")
                
                # Stage 4: Use database and schema
                logger.info("\n[4/6] Setting database and schema context...")
                if not creator.use_database():
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error="Failed to use database",
                        details=details
                    )
                
                if not creator.use_schema():
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error="Failed to use schema",
                        details=details
                    )
                stages_completed.append("set_context")
                
                # Stage 5: Create tables
                logger.info("\n[5/6] Creating tables...")
                tables_success = creator.create_tables()
                stages_completed.append("create_tables")
                
                details["tables_created"] = creator.stats["tables_created"]
                details["tables_failed"] = creator.stats["tables_failed"]
                details["new_tables_created"] = creator.stats["new_tables_created"]
                
                if not tables_success:
                    return self._create_result(
                        success=False,
                        started_at=started_at,
                        stages_completed=stages_completed,
                        error=f"Failed to create {creator.stats['tables_failed']} tables",
                        details=details
                    )
                
                # Stage 6: Apply foreign keys
                if config.apply_foreign_keys:
                    logger.info("\n[6/6] Applying foreign key constraints...")
                    fk_success = creator.apply_foreign_keys()
                    stages_completed.append("apply_fks")
                    
                    details["fks_applied"] = creator.stats["constraints_applied"]
                    details["fks_failed"] = creator.stats["constraints_failed"]
                    
                    if not fk_success:
                        logger.warning(f"Some FK constraints failed: {creator.stats['constraints_failed']}")
                else:
                    logger.info("\n[6/6] Skipping FK constraints (apply_foreign_keys=False)")
                    stages_completed.append("skip_fks")
                
                # Validate creation
                validation = creator.validate_creation()
                details["validation"] = validation
                
                result = self._create_result(
                    success=True,
                    started_at=started_at,
                    stages_completed=stages_completed,
                    details=details
                )
                
                self._log_end(result)
                return result
                
        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            return self._create_result(
                success=False,
                started_at=started_at,
                stages_completed=stages_completed,
                error=str(e),
                details=details
            )
    
    def _execute_dry_run(
        self,
        config: TableSetupConfig,
        started_at: datetime
    ) -> WorkflowResult:
        """
        Execute a dry run showing what would be done.
        
        Args:
            config: Workflow configuration
            started_at: Workflow start time
            
        Returns:
            WorkflowResult for dry run
        """
        logger.info("\n" + "=" * 80)
        logger.info("DRY RUN - No changes will be made")
        logger.info("=" * 80)
        
        schema_manager = SchemaManager()
        tables = schema_manager.all_tables
        
        logger.info(f"\nWould create {len(tables)} tables:")
        for table in tables:
            logger.info(f"  - {table.table_name}")
        
        # Get FK scripts
        fk_scripts = schema_manager.get_foreign_key_scripts()
        logger.info(f"\nWould apply {len(fk_scripts)} foreign key constraints")
        
        if config.drop_existing:
            logger.info("\nWould drop existing tables before creation (drop_existing=True)")
        
        details = {
            "dry_run": True,
            "tables_to_create": [t.table_name for t in tables],
            "fk_count": len(fk_scripts)
        }
        
        result = self._create_result(
            success=True,
            started_at=started_at,
            stages_completed=["dry_run"],
            details=details
        )
        
        self._log_end(result)
        return result
    
    def _drop_existing_tables(
        self,
        creator: TableCreator,
        existing_tables: List[str]
    ) -> None:
        """
        Drop existing tables in reverse FK order.
        
        Args:
            creator: TableCreator instance
            existing_tables: List of existing table names
        """
        if not existing_tables:
            logger.info("No existing tables to drop")
            return
        
        # Get tables in creation order and reverse for drops
        schema_manager = SchemaManager()
        all_tables = [t.table_name for t in schema_manager.all_tables]
        
        # Drop in reverse order (bridge -> fact -> dimension)
        drop_order = list(reversed(all_tables))
        
        if creator.platform == "postgres":
            qualified_prefix = creator.schema_name
        else:
            qualified_prefix = f"{creator.database_name}.{creator.schema_name}"

        for table_name in drop_order:
            if table_name.lower() in [t.lower() for t in existing_tables]:
                try:
                    qualified_name = f"{qualified_prefix}.{table_name}"
                    logger.info(f"Dropping table: {qualified_name}")
                    creator.connector.execute_query(f"DROP TABLE IF EXISTS {qualified_name} CASCADE")
                    if creator.platform == "postgres":
                        creator.connector.commit()
                except Exception as e:
                    logger.warning(f"Failed to drop {table_name}: {e}")
                    if creator.platform == "postgres":
                        try:
                            creator.connector.rollback()
                        except Exception:
                            pass


# Backwards compatibility aliases
SchemaCreationWorkflow = TableSetupWorkflow
SchemaWorkflowConfig = TableSetupConfig
