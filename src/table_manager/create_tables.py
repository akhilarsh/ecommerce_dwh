"""
Table Creation Module.

Platform-aware table creation supporting Snowflake and PostgreSQL.
Verifies connection, database/schema existence, creates tables in
dependency order, and applies foreign key constraints.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.connectors.base_connector import BaseConnector
from src.sql_generator.schema_manager import SchemaManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = project_root / "outputs" / "generated_sql"


class TableCreator:
    """Handles table creation across Snowflake and PostgreSQL."""

    def __init__(
        self,
        connector: BaseConnector,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None,
    ):
        self.connector = connector
        self.platform = connector.PLATFORM
        self.schema_manager = SchemaManager()

        db, schema = self._resolve_db_schema(database_name, schema_name)
        self.database_name = db
        self.schema_name = schema

        self.stats = {
            "connection_verified": False,
            "database_exists": False,
            "schema_exists": False,
            "tables_created": 0,
            "tables_failed": 0,
            "constraints_applied": 0,
            "constraints_failed": 0,
            "errors": [],
            "new_tables_created": [],
        }

        self.pre_creation_status = {
            "database_available": False,
            "schema_exists": False,
            "existing_tables": [],
            "tables_to_create": [],
        }

    def _resolve_db_schema(
        self, database_name: Optional[str], schema_name: Optional[str]
    ) -> tuple:
        if self.platform == "snowflake":
            db = (database_name or os.getenv("SNOWFLAKE_DATABASE", "")).lower()
            schema = (schema_name or os.getenv("SNOWFLAKE_SCHEMA", "")).lower()
            if not db:
                raise ValueError("SNOWFLAKE_DATABASE environment variable is required")
            if not schema:
                raise ValueError("SNOWFLAKE_SCHEMA environment variable is required")
            return db, schema

        if self.platform == "postgres":
            db = (database_name or os.getenv("POSTGRES_DATABASE", "")).lower()
            schema = (schema_name or os.getenv("POSTGRES_SCHEMA", "public")).lower()
            if not db:
                raise ValueError("POSTGRES_DATABASE environment variable is required")
            return db, schema

        if self.platform == "databricks":
            db = (database_name or os.getenv("DATABRICKS_CATALOG", "")).lower()
            schema = (schema_name or os.getenv("DATABRICKS_SCHEMA", "ecommerce_dwh")).lower()
            if not db:
                raise ValueError("DATABRICKS_CATALOG environment variable is required")
            return db, schema

        if self.platform == "bigquery":
            # BigQuery project ids are case-sensitive (typically lowercase with hyphens).
            db = database_name or os.getenv("BIGQUERY_PROJECT", "")
            schema = schema_name or os.getenv("BIGQUERY_DATASET", "ecommerce_dwh")
            if not db:
                raise ValueError("BIGQUERY_PROJECT environment variable is required")
            return db, schema

        if self.platform == "redshift":
            db = (database_name or os.getenv("REDSHIFT_DATABASE", "")).lower()
            schema = (schema_name or os.getenv("REDSHIFT_SCHEMA", "ecommerce_dwh")).lower()
            if not db:
                raise ValueError("REDSHIFT_DATABASE environment variable is required")
            return db, schema

        raise ValueError(f"Unsupported platform: {self.platform}")

    # ------------------------------------------------------------------
    # SQL file helpers
    # ------------------------------------------------------------------

    def _save_sql_to_file(self, sql_statements: List[str], filename: str) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / filename

        content = ";\n\n".join(sql_statements)
        if content and not content.endswith(";"):
            content += ";"

        output_path.write_text(content)
        logger.info(f"Saved SQL to: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Connection verification (platform-aware)
    # ------------------------------------------------------------------

    def verify_connection(self, table_filter: Optional[str] = None) -> Dict[str, Any]:
        logger.info("=" * 80)
        logger.info("CONNECTION VERIFICATION & STATUS CHECK")
        logger.info("=" * 80)

        status: Dict[str, Any] = {
            "connection_ok": False,
            "database_exists": False,
            "schema_exists": False,
            "existing_tables": [],
            "missing_tables": [],
            "warehouse_active": False,
        }

        try:
            if self.platform == "snowflake":
                self._verify_snowflake(status)
            elif self.platform == "postgres":
                self._verify_postgres(status)
            elif self.platform == "databricks":
                self._verify_databricks(status)
            elif self.platform == "bigquery":
                self._verify_bigquery(status)
            elif self.platform == "redshift":
                self._verify_redshift(status)

            if not status["connection_ok"] or not status["database_exists"] or not status["schema_exists"]:
                return status

            existing_tables = self._get_existing_tables()
            status["existing_tables"] = existing_tables or []
            self.pre_creation_status["existing_tables"] = existing_tables or []

            all_expected = [t.table_name for t in self.schema_manager.all_tables]

            if table_filter:
                if table_filter.lower() not in [t.lower() for t in all_expected]:
                    logger.error(f"  ✗ Table '{table_filter}' not found in schema definition")
                    status["table_not_found"] = True
                    return status
                expected_tables = [t for t in all_expected if t.lower() == table_filter.lower()]
            else:
                expected_tables = all_expected

            existing_lower = {t.lower() for t in (existing_tables or [])}
            for tbl_name in expected_tables:
                if tbl_name.lower() in existing_lower:
                    logger.info(f"  ✓ {tbl_name} - EXISTS")
                else:
                    logger.info(f"  ○ {tbl_name} - TO BE CREATED")
                    status["missing_tables"].append(tbl_name)
                    self.pre_creation_status["tables_to_create"].append(tbl_name)

            existing_count = len([t for t in expected_tables if t.lower() in existing_lower])
            logger.info(f"\n  Summary: {existing_count} existing, {len(status['missing_tables'])} to create")
            self.stats["connection_verified"] = True
            logger.info("\n" + "=" * 80)

        except Exception as e:
            error_msg = f"Connection verification failed: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)

        return status

    def _verify_snowflake(self, status: Dict[str, Any]) -> None:
        logger.info("Testing Snowflake connection...")
        result = self.connector.execute_query(
            "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()"
        )
        if result:
            user, role, warehouse = result[0]
            logger.info(f"  ✓ Connected as user: {user}")
            logger.info(f"  ✓ Current role: {role}")
            logger.info(f"  ✓ Current warehouse: {warehouse}")
            status["connection_ok"] = True
            status["warehouse_active"] = warehouse is not None

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
            return

        self.connector.execute_query(f"USE DATABASE {self.database_name}")

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

    def _verify_databricks(self, status: Dict[str, Any]) -> None:
        logger.info("Testing Databricks connection...")
        result = self.connector.execute_query(
            "SELECT current_user(), current_catalog(), current_schema()"
        )
        if result:
            user, catalog, schema = result[0]
            logger.info(f"  ✓ Connected as user: {user}")
            logger.info(f"  ✓ Catalog: {catalog}")
            logger.info(f"  ✓ Schema: {schema}")
            status["connection_ok"] = True

        logger.info(f"\nChecking catalog: {self.database_name}")
        catalog_check = self.connector.execute_query(
            "SELECT 1 FROM information_schema.catalogs WHERE catalog_name = ?",
            (self.database_name,),
        )
        if catalog_check and len(catalog_check) > 0:
            logger.info(f"  ✓ Catalog '{self.database_name}' exists")
            status["database_exists"] = True
            self.pre_creation_status["database_available"] = True
        else:
            logger.warning(f"  ✗ Catalog '{self.database_name}' NOT FOUND")
            return

        logger.info(f"\nChecking schema: {self.schema_name}")
        schema_check = self.connector.execute_query(
            "SELECT 1 FROM information_schema.schemata "
            "WHERE catalog_name = ? AND schema_name = ?",
            (self.database_name, self.schema_name),
        )
        if schema_check and len(schema_check) > 0:
            logger.info(f"  ✓ Schema '{self.schema_name}' exists")
            status["schema_exists"] = True
            self.pre_creation_status["schema_exists"] = True
        else:
            logger.warning(f"  ✗ Schema '{self.schema_name}' NOT FOUND")

    def _verify_bigquery(self, status: Dict[str, Any]) -> None:
        logger.info("Testing BigQuery connection...")
        # Use a SELECT 1 round-trip; BigQuery clients lazily authenticate
        # until the first query.
        result = self.connector.execute_query("SELECT 1")
        if result:
            logger.info(f"  ✓ Connected to BigQuery project: {self.database_name}")
            status["connection_ok"] = True

        # BigQuery project always "exists" by virtue of the client being able
        # to connect. We trust the configured project id.
        status["database_exists"] = True
        self.pre_creation_status["database_available"] = True

        logger.info(f"\nChecking dataset: {self.schema_name}")
        try:
            from google.cloud.exceptions import NotFound
            self.connector.client.get_dataset(
                f"{self.database_name}.{self.schema_name}"
            )
            logger.info(f"  ✓ Dataset '{self.schema_name}' exists")
            status["schema_exists"] = True
            self.pre_creation_status["schema_exists"] = True
        except NotFound:
            logger.warning(f"  ✗ Dataset '{self.schema_name}' NOT FOUND")

    def _verify_redshift(self, status: Dict[str, Any]) -> None:
        logger.info("Testing Redshift connection...")
        result = self.connector.execute_query(
            "SELECT current_user, current_database()"
        )
        if result:
            user, database = result[0]
            logger.info(f"  ✓ Connected as user: {user}")
            logger.info(f"  ✓ Database: {database}")
            status["connection_ok"] = True

        # Redshift connection is bound to a single database.
        status["database_exists"] = True
        self.pre_creation_status["database_available"] = True

        logger.info(f"\nChecking schema: {self.schema_name}")
        schema_check = self.connector.execute_query(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
            (self.schema_name,),
        )
        if schema_check and len(schema_check) > 0:
            logger.info(f"  ✓ Schema '{self.schema_name}' exists")
            status["schema_exists"] = True
            self.pre_creation_status["schema_exists"] = True
        else:
            logger.warning(f"  ✗ Schema '{self.schema_name}' NOT FOUND")

    def _verify_postgres(self, status: Dict[str, Any]) -> None:
        logger.info("Testing PostgreSQL connection...")
        result = self.connector.execute_query("SELECT current_user, current_database()")
        if result:
            user, database = result[0]
            logger.info(f"  ✓ Connected as user: {user}")
            logger.info(f"  ✓ Database: {database}")
            status["connection_ok"] = True

        # PG is already connected to a specific database
        status["database_exists"] = True
        self.pre_creation_status["database_available"] = True

        logger.info(f"\nChecking schema: {self.schema_name}")
        schema_check = self.connector.execute_query(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
            (self.schema_name,),
        )
        if schema_check and len(schema_check) > 0:
            logger.info(f"  ✓ Schema '{self.schema_name}' exists")
            status["schema_exists"] = True
            self.pre_creation_status["schema_exists"] = True
        else:
            logger.warning(f"  ✗ Schema '{self.schema_name}' NOT FOUND")

    # ------------------------------------------------------------------
    # use_database / use_schema (platform-aware)
    # ------------------------------------------------------------------

    def use_database(self) -> bool:
        try:
            if self.platform == "snowflake":
                logger.info(f"Using database: {self.database_name}")
                db_check = self.connector.execute_query(
                    f"SHOW DATABASES LIKE '{self.database_name}'"
                )
                if not db_check or len(db_check) == 0:
                    error_msg = f"Database '{self.database_name}' does not exist."
                    logger.error(error_msg)
                    self.stats["errors"].append(error_msg)
                    return False
                self.connector.execute_query(f"USE DATABASE {self.database_name}")
            elif self.platform == "databricks":
                logger.info(f"Using catalog: {self.database_name}")
                self.connector.execute_query(f"USE CATALOG `{self.database_name}`")
            elif self.platform == "bigquery":
                # BigQuery has no `USE PROJECT` concept — the client is bound
                # to the project at connection time.
                logger.info(f"BigQuery project bound at connection: {self.database_name}")
            elif self.platform == "redshift":
                # Redshift connection is already bound to a single database.
                logger.info(f"Redshift database bound at connection: {self.database_name}")
            # PG: no-op — already connected to the database
            logger.info(f"✓ Database '{self.database_name}' ready")
            self.stats["database_exists"] = True
            return True

        except Exception as e:
            error_msg = f"Failed to use database: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False

    def use_schema(self) -> bool:
        try:
            if self.platform == "snowflake":
                logger.info(f"Using schema: {self.schema_name}")
                schema_check = self.connector.execute_query(
                    f"SHOW SCHEMAS LIKE '{self.schema_name}' IN DATABASE {self.database_name}"
                )
                if not schema_check or len(schema_check) == 0:
                    error_msg = f"Schema '{self.schema_name}' does not exist."
                    logger.error(error_msg)
                    self.stats["errors"].append(error_msg)
                    return False
                self.connector.execute_query(f"USE SCHEMA {self.schema_name}")

            elif self.platform == "postgres":
                logger.info(f"Setting search_path to: {self.schema_name}")
                self.connector.execute_query(
                    f"SET search_path TO {self.schema_name}, public"
                )

            elif self.platform == "databricks":
                logger.info(f"Using schema: {self.schema_name}")
                self.connector.execute_query(f"USE SCHEMA `{self.schema_name}`")

            elif self.platform == "bigquery":
                # BigQuery datasets are referenced by 3-part name in every
                # query; there is no `USE SCHEMA`. No-op.
                logger.info(
                    f"BigQuery dataset will be referenced as "
                    f"`{self.database_name}.{self.schema_name}`"
                )

            elif self.platform == "redshift":
                logger.info(f"Setting search_path to: {self.schema_name}")
                self.connector.execute_query(
                    f'SET search_path TO "{self.schema_name}", public'
                )
                self.connector.commit()

            logger.info(f"✓ Schema '{self.schema_name}' ready")
            self.stats["schema_exists"] = True
            return True

        except Exception as e:
            error_msg = f"Failed to use schema: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False

    # ------------------------------------------------------------------
    # Table creation (platform-aware DDL)
    # ------------------------------------------------------------------

    def _get_create_scripts(self, table_filter: Optional[str] = None) -> List[str]:
        """Get CREATE TABLE scripts appropriate for the platform."""
        if self.platform == "postgres":
            from src.sql_generator.pg_ddl_adapter import generate_pg_create_table

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                create_sql, comment_stmts = generate_pg_create_table(table, self.schema_name)
                scripts.append(create_sql)
                scripts.extend(comment_stmts)
            return scripts

        if self.platform == "databricks":
            from src.sql_generator.dbx_ddl_adapter import generate_dbx_create_table

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                create_sql, _ = generate_dbx_create_table(
                    table, self.database_name, self.schema_name
                )
                scripts.append(create_sql)
            return scripts

        if self.platform == "bigquery":
            from src.sql_generator.bq_ddl_adapter import generate_bq_create_table

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                create_sql, _ = generate_bq_create_table(
                    table, self.database_name, self.schema_name
                )
                scripts.append(create_sql)
            return scripts

        if self.platform == "redshift":
            from src.sql_generator.rs_ddl_adapter import generate_rs_create_table

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                create_sql, comment_stmts = generate_rs_create_table(
                    table, self.schema_name
                )
                scripts.append(create_sql)
                scripts.extend(comment_stmts)
            return scripts

        return self.schema_manager.get_create_table_scripts(table_filter)

    def _get_fk_scripts(self, table_filter: Optional[str] = None) -> List[str]:
        """Get FK scripts appropriate for the platform."""
        if self.platform == "postgres":
            from src.sql_generator.pg_ddl_adapter import generate_pg_foreign_keys

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                scripts.extend(generate_pg_foreign_keys(table, self.schema_name))
            return scripts

        if self.platform == "databricks":
            from src.sql_generator.dbx_ddl_adapter import generate_dbx_foreign_keys

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                scripts.extend(
                    generate_dbx_foreign_keys(
                        table, self.database_name, self.schema_name
                    )
                )
            return scripts

        if self.platform == "bigquery":
            from src.sql_generator.bq_ddl_adapter import generate_bq_foreign_keys

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                scripts.extend(
                    generate_bq_foreign_keys(
                        table, self.database_name, self.schema_name
                    )
                )
            return scripts

        if self.platform == "redshift":
            from src.sql_generator.rs_ddl_adapter import generate_rs_foreign_keys

            tables = self.schema_manager.all_tables
            if table_filter:
                tables = [t for t in tables if t.table_name.lower() == table_filter.lower()]

            scripts: List[str] = []
            for table in tables:
                scripts.extend(generate_rs_foreign_keys(table, self.schema_name))
            return scripts

        return self.schema_manager.get_foreign_key_scripts(table_filter)

    def create_tables(self, table_filter: Optional[str] = None) -> bool:
        logger.info("=" * 80)
        logger.info("CREATING TABLES")
        logger.info("=" * 80)

        create_scripts = self._get_create_scripts(table_filter)

        if table_filter and not create_scripts:
            logger.error(f"Table '{table_filter}' not found in schema")
            self.stats["errors"].append(f"Table '{table_filter}' not found")
            return False

        logger.info(f"Total statements to execute: {len(create_scripts)}")

        if table_filter:
            filename = f"01_create_{table_filter.lower()}.sql"
        else:
            filename = "01_create_tables.sql"
        self._save_sql_to_file(create_scripts, filename)

        existing_tables = self._get_existing_tables()
        existing_tables_lower = {t.lower() for t in existing_tables} if existing_tables else set()

        success = True
        skipped = 0
        for i, sql in enumerate(create_scripts, 1):
            # Skip COMMENT ON statements in skip-check logic
            if sql.strip().upper().startswith("COMMENT ON"):
                try:
                    self.connector.execute_query(sql)
                    if self.platform in ("postgres", "redshift"):
                        self.connector.commit()
                except Exception:
                    pass  # non-critical
                continue

            table_name = self._extract_table_name(sql)

            if existing_tables_lower and table_name.lower() in existing_tables_lower:
                logger.info(f"[{i}/{len(create_scripts)}] ⊘ Table '{table_name}' already exists, skipping")
                skipped += 1
                continue

            try:
                logger.info(f"[{i}/{len(create_scripts)}] Creating table: {table_name}")
                self.connector.execute_query(sql)
                if self.platform in ("postgres", "redshift"):
                    self.connector.commit()
                self.stats["tables_created"] += 1
                self.stats["new_tables_created"].append(table_name)
                logger.info(f"✓ Table '{table_name}' created successfully")

            except Exception as e:
                error_str = str(e)
                if "already exists" in error_str.lower() or "42710" in error_str or "42P07" in error_str:
                    logger.info(f"⊘ Table '{table_name}' already exists, skipping")
                    if self.platform in ("postgres", "redshift"):
                        self.connector.rollback()
                    skipped += 1
                    continue

                error_msg = f"Failed to create table '{table_name}': {e}"
                logger.error(f"✗ {error_msg}")
                if self.platform in ("postgres", "redshift"):
                    self.connector.rollback()
                self.stats["tables_failed"] += 1
                self.stats["errors"].append(error_msg)
                success = False
                continue

        logger.info(f"\nTables: {self.stats['tables_created']} created, {skipped} already existed")
        return success

    def _get_existing_tables(self) -> Optional[List[str]]:
        try:
            if self.platform == "snowflake":
                result = self.connector.execute_query(f"""
                    SELECT TABLE_NAME
                    FROM {self.database_name}.INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = '{self.schema_name.upper()}'
                """)
                return [row[0].lower() for row in result] if result else []

            if self.platform == "postgres":
                result = self.connector.execute_query(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (self.schema_name,),
                )
                return [row[0] for row in result] if result else []

            if self.platform == "databricks":
                result = self.connector.execute_query(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_catalog = ? AND table_schema = ?",
                    (self.database_name, self.schema_name),
                )
                return [row[0] for row in result] if result else []

            if self.platform == "bigquery":
                result = self.connector.execute_query(
                    f"SELECT table_name FROM "
                    f"`{self.database_name}.{self.schema_name}.INFORMATION_SCHEMA.TABLES`"
                )
                return [row[0] for row in result] if result else []

            if self.platform == "redshift":
                result = self.connector.execute_query(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s",
                    (self.schema_name,),
                )
                return [row[0] for row in result] if result else []

            return []
        except Exception as e:
            logger.error(f"Failed to query existing tables: {e}")
            return None

    def apply_foreign_keys(self, table_filter: Optional[str] = None) -> bool:
        logger.info("=" * 80)
        logger.info("APPLYING FOREIGN KEY CONSTRAINTS")
        logger.info("=" * 80)

        fk_scripts = self._get_fk_scripts(table_filter)

        if not fk_scripts:
            logger.info("No foreign keys to apply for this table")
            return True

        logger.info(f"Total foreign keys to create: {len(fk_scripts)}")

        if table_filter:
            filename = f"02_foreign_keys_{table_filter.lower()}.sql"
        else:
            filename = "02_foreign_keys.sql"
        self._save_sql_to_file(fk_scripts, filename)

        success = True
        skipped = 0
        for i, sql in enumerate(fk_scripts, 1):
            constraint_info = self._extract_constraint_info(sql)

            try:
                logger.info(f"[{i}/{len(fk_scripts)}] Adding FK: {constraint_info}")
                self.connector.execute_query(sql)
                if self.platform in ("postgres", "redshift"):
                    self.connector.commit()
                self.stats["constraints_applied"] += 1
                logger.info("✓ Foreign key added successfully")

            except Exception as e:
                error_str = str(e)
                if "already exists" in error_str.lower() or "42710" in error_str or "42710" in error_str:
                    logger.info(f"⊘ Foreign key '{constraint_info}' already exists, skipping")
                    if self.platform in ("postgres", "redshift"):
                        self.connector.rollback()
                    skipped += 1
                    continue

                error_msg = f"Failed to add foreign key '{constraint_info}': {e}"
                logger.error(f"✗ {error_msg}")
                if self.platform in ("postgres", "redshift"):
                    self.connector.rollback()
                self.stats["constraints_failed"] += 1
                self.stats["errors"].append(error_msg)
                success = False
                continue

        logger.info(f"\nForeign keys: {self.stats['constraints_applied']} added, {skipped} already existed")
        return success

    def validate_creation(self) -> Dict[str, Any]:
        logger.info("=" * 80)
        logger.info("VALIDATING TABLE CREATION")
        logger.info("=" * 80)

        validation: Dict[str, Any] = {
            "tables_found": [],
            "tables_missing": [],
            "total_expected": len(self.schema_manager.all_tables),
        }

        for table in self.schema_manager.all_tables:
            tbl = table.table_name
            try:
                if self.platform == "snowflake":
                    sql = f"""
                        SELECT COUNT(*)
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_SCHEMA = '{self.schema_name.upper()}'
                        AND TABLE_NAME = '{tbl.upper()}'
                    """
                    result = self.connector.execute_query(sql)
                elif self.platform == "postgres":
                    result = self.connector.execute_query(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = %s AND table_name = %s",
                        (self.schema_name, tbl),
                    )
                elif self.platform == "databricks":
                    result = self.connector.execute_query(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_catalog = ? AND table_schema = ? AND table_name = ?",
                        (self.database_name, self.schema_name, tbl),
                    )
                elif self.platform == "bigquery":
                    result = self.connector.execute_query(
                        f"SELECT COUNT(*) FROM "
                        f"`{self.database_name}.{self.schema_name}.INFORMATION_SCHEMA.TABLES` "
                        f"WHERE table_name = '{tbl}'"
                    )
                elif self.platform == "redshift":
                    result = self.connector.execute_query(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = %s AND table_name = %s",
                        (self.schema_name, tbl),
                    )
                else:
                    result = None

                if result and result[0][0] > 0:
                    validation["tables_found"].append(tbl)
                    logger.info(f"✓ Table '{tbl}' exists")
                else:
                    validation["tables_missing"].append(tbl)
                    logger.warning(f"✗ Table '{tbl}' NOT FOUND")

            except Exception as e:
                logger.error(f"Error checking table '{tbl}': {e}")
                validation["tables_missing"].append(tbl)

        validation["total_found"] = len(validation["tables_found"])
        validation["total_missing"] = len(validation["tables_missing"])

        logger.info(f"\nValidation Summary:")
        logger.info(f"  Expected: {validation['total_expected']} tables")
        logger.info(f"  Found: {validation['total_found']} tables")
        logger.info(f"  Missing: {validation['total_missing']} tables")

        return validation

    def get_creation_summary(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "database": self.database_name,
            "schema": self.schema_name,
            "platform": self.platform,
            "pre_creation_status": self.pre_creation_status.copy(),
            "statistics": self.stats.copy(),
            "success": (
                self.stats["database_exists"]
                and self.stats["schema_exists"]
                and self.stats["tables_failed"] == 0
            ),
        }

    def _extract_table_name(self, sql: str) -> str:
        try:
            upper_sql = sql.upper()
            if "IF NOT EXISTS" in upper_sql:
                idx = upper_sql.find("IF NOT EXISTS") + len("IF NOT EXISTS")
                remaining = sql[idx:].strip()
                full_name = remaining.split()[0].split("(")[0].strip()
            else:
                parts = sql.split()
                for i, part in enumerate(parts):
                    if part.upper() == "TABLE":
                        full_name = parts[i + 1].strip("(").strip()
                        break
                else:
                    return "UNKNOWN"

            if "." in full_name:
                return full_name.split(".")[-1]
            return full_name
        except Exception:
            return "UNKNOWN"

    def _extract_constraint_info(self, sql: str) -> str:
        try:
            if "CONSTRAINT" in sql:
                parts = sql.split("CONSTRAINT")
                if len(parts) > 1:
                    return parts[1].split()[0].strip()
            return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def create_all(self, apply_fks: bool = True) -> bool:
        logger.info("=" * 80)
        logger.info("STARTING TABLE CREATION")
        logger.info("=" * 80)
        logger.info(f"Platform: {self.platform}")
        logger.info(f"Database: {self.database_name}")
        logger.info(f"Schema: {self.schema_name}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        connection_status = self.verify_connection()
        if not connection_status["connection_ok"]:
            logger.error("Connection verification failed. Aborting.")
            return False

        if not connection_status["database_exists"]:
            logger.error(f"Database '{self.database_name}' does not exist. Aborting.")
            return False

        if not self.use_database():
            logger.error("Failed to use database. Aborting.")
            return False

        if not connection_status["schema_exists"]:
            logger.error(f"Schema '{self.schema_name}' does not exist. Aborting.")
            return False

        if not self.use_schema():
            logger.error("Failed to use schema. Aborting.")
            return False

        tables_success = self.create_tables()

        fk_success = True
        if apply_fks:
            fk_success = self.apply_foreign_keys()
        else:
            logger.info("Skipping foreign key constraints (apply_fks=False)")

        validation = self.validate_creation()
        self._print_creation_summary(validation)

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
        logger.info("=" * 80)
        logger.info("CREATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Platform: {self.platform}")
        logger.info(f"Database: {self.database_name} - {'✓' if self.stats['database_exists'] else '✗'}")
        logger.info(f"Schema: {self.schema_name} - {'✓' if self.stats['schema_exists'] else '✗'}")
        logger.info(f"Tables Created: {self.stats['tables_created']}")
        logger.info(f"Tables Failed: {self.stats['tables_failed']}")
        logger.info(f"Foreign Keys Applied: {self.stats['constraints_applied']}")
        logger.info(f"Foreign Keys Failed: {self.stats['constraints_failed']}")
        logger.info(f"Tables Validated: {validation['total_found']}/{validation['total_expected']}")

        if self.stats["errors"]:
            logger.info(f"\nErrors encountered: {len(self.stats['errors'])}")
            for i, error in enumerate(self.stats["errors"][:5], 1):
                logger.error(f"  {i}. {error}")
            if len(self.stats["errors"]) > 5:
                logger.error(f"  ... and {len(self.stats['errors']) - 5} more errors")


def main():
    """Main execution function."""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        from src.connectors import get_connector
        from src.cli.config import get_dwh_platform

        logger.info("Initializing table creation...")
        platform = get_dwh_platform()

        connector = get_connector(platform)
        with connector:
            creator = TableCreator(connector)
            success = creator.create_all(apply_fks=True)

            if success:
                logger.info("\n" + "=" * 80)
                logger.info("Table Creation - COMPLETE ✓")
                logger.info("=" * 80)
                return 0
            else:
                logger.error("\n" + "=" * 80)
                logger.error("Table Creation - FAILED ✗")
                logger.error("=" * 80)
                return 1

    except Exception as e:
        logger.error(f"Fatal error during table creation: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
