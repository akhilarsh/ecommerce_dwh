"""
Validate command for checking table creation status.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.connectors import get_connector
from src.connectors.base_connector import BaseConnector
from src.cli.config import get_dwh_platform
from src.sql_generator.schema_manager import SchemaManager

logger = get_logger(__name__)
console = Console()


def validate_command(
    check_fk: bool = False,
    check_data: bool = False,
    verbose: bool = False
) -> bool:
    """
    Validate table creation - check tables and optionally constraints/data.
    
    Args:
        check_fk: Validate foreign key constraints
        check_data: Check for data presence
        verbose: Enable verbose output
        
    Returns:
        True if validation passes, False otherwise
    """
    console.print("\n[bold]Validating Table Creation...[/bold]\n")
    
    try:
        platform = get_dwh_platform()
        connector = get_connector(platform)
        schema_manager = SchemaManager()
        expected_tables = [t.table_name for t in schema_manager.all_tables]

        is_snowflake = platform in ("sf", "snowflake")
        is_databricks = platform in ("db", "dbx", "databricks")
        is_bigquery = platform in ("bq", "bigquery")
        is_redshift = platform in ("rs", "redshift")

        with connector:
            # Get current database/catalog and schema (platform-specific —
            # Databricks errors on "duplicate field names" without aliases).
            if is_snowflake:
                db_result = connector.execute_query(
                    "SELECT CURRENT_DATABASE() AS db, CURRENT_SCHEMA() AS sch"
                )
            elif is_databricks:
                db_result = connector.execute_query(
                    "SELECT current_catalog() AS cat, current_schema() AS sch"
                )
            elif is_bigquery:
                # BigQuery has no SESSION_USER concept of "current" project /
                # dataset — it's defined on the client. Read from the connector.
                db_result = [(connector.project, connector.dataset)]
            else:
                db_result = connector.execute_query(
                    "SELECT current_database() AS db, current_schema() AS sch"
                )
            if db_result:
                database, schema = db_result[0]
                if is_databricks:
                    label = "Catalog"
                elif is_bigquery:
                    label = "Project"
                else:
                    label = "Database"
                console.print(f"[dim]{label}: {database}[/dim]")
                console.print(f"[dim]Schema: {schema}[/dim]\n")

            # Check tables
            console.print("[bold]Checking tables...[/bold]\n")

            if is_snowflake:
                tables_query = f"""
                    SELECT TABLE_NAME, ROW_COUNT, BYTES
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = UPPER('{schema}')
                    ORDER BY TABLE_NAME
                """
                result = connector.execute_query(tables_query)
                existing_tables = {row[0].lower(): {"rows": row[1], "bytes": row[2]} for row in result} if result else {}
            elif is_databricks:
                tables_query = f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_catalog = '{database}'
                      AND table_schema = '{schema}'
                      AND table_type = 'MANAGED'
                    ORDER BY table_name
                """
                result = connector.execute_query(tables_query)
                # Row counts aren't in information_schema; populated below per-table.
                existing_tables = {row[0].lower(): {"rows": None, "bytes": None} for row in result} if result else {}
                for tbl_lower in list(existing_tables.keys()):
                    try:
                        r = connector.execute_query(
                            f"SELECT COUNT(*) FROM {database}.{schema}.{tbl_lower}"
                        )
                        existing_tables[tbl_lower]["rows"] = r[0][0] if r else 0
                    except Exception as e:
                        logger.debug(f"COUNT(*) failed for {tbl_lower}: {e}")
                        existing_tables[tbl_lower]["rows"] = 0
            elif is_bigquery:
                # BigQuery's legacy __TABLES__ exposes row_count + size_bytes
                # but uses `table_id` (not `table_name`) as the column.
                tables_query = f"""
                    SELECT table_id, row_count, size_bytes
                    FROM `{database}.{schema}.__TABLES__`
                    ORDER BY table_id
                """
                result = connector.execute_query(tables_query)
                existing_tables = (
                    {row[0].lower(): {"rows": row[1], "bytes": row[2]} for row in result}
                    if result else {}
                )
            elif is_redshift:
                # Redshift has no pg_stat_user_tables; size lives in
                # SVV_TABLE_INFO. Row counts are filled in per-table below.
                tables_query = f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = '{schema}'
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """
                result = connector.execute_query(tables_query)
                existing_tables = {
                    row[0].lower(): {"rows": None, "bytes": None}
                    for row in result
                } if result else {}
                for tbl_lower in list(existing_tables.keys()):
                    try:
                        r = connector.execute_query(
                            f'SELECT COUNT(*) FROM "{schema}"."{tbl_lower}"'
                        )
                        existing_tables[tbl_lower]["rows"] = r[0][0] if r else 0
                    except Exception as e:
                        logger.debug(f"COUNT(*) failed for {tbl_lower}: {e}")
                        existing_tables[tbl_lower]["rows"] = 0
            else:
                tables_query = f"""
                    SELECT t.table_name, COALESCE(s.n_live_tup, 0), NULL
                    FROM information_schema.tables t
                    LEFT JOIN pg_stat_user_tables s
                        ON s.relname = t.table_name AND s.schemaname = t.table_schema
                    WHERE t.table_schema = '{schema}'
                    AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name
                """
                result = connector.execute_query(tables_query)
                existing_tables = {row[0].lower(): {"rows": row[1], "bytes": row[2]} for row in result} if result else {}
            
            # Display table status
            table = Table(title="Table Status", show_header=True)
            table.add_column("Table Name", style="cyan")
            table.add_column("Status", style="white")
            table.add_column("Rows", justify="right")
            table.add_column("Size", justify="right")
            
            missing_tables = []
            found_tables = []
            
            for expected_table in expected_tables:
                if expected_table.lower() in existing_tables:
                    info = existing_tables[expected_table.lower()]
                    rows = info["rows"] or 0
                    size = format_bytes(info["bytes"]) if info["bytes"] else "0 B"
                    table.add_row(expected_table, "[green]✓ EXISTS[/green]", str(rows), size)
                    found_tables.append(expected_table)
                else:
                    table.add_row(expected_table, "[red]✗ MISSING[/red]", "-", "-")
                    missing_tables.append(expected_table)
            
            console.print(table)
            
            # Summary
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  Expected tables: {len(expected_tables)}")
            console.print(f"  Found: [green]{len(found_tables)}[/green]")
            console.print(f"  Missing: [red]{len(missing_tables)}[/red]")
            
            # Check foreign keys if requested
            fk_valid = True
            if check_fk and found_tables:
                console.print("\n[bold]Checking foreign keys...[/bold]\n")
                fk_valid = check_foreign_keys(
                    connector, schema, platform, verbose, database=database
                )

            # Check data if requested
            data_valid = True
            if check_data and found_tables:
                console.print("\n[bold]Checking data presence...[/bold]\n")
                data_valid = check_table_data(
                    connector, schema, found_tables, database=database, platform=platform
                )
            
            # Final result
            all_valid = len(missing_tables) == 0 and fk_valid and data_valid
            
            if all_valid:
                console.print("\n[bold green]✓ Validation passed![/bold green]\n")
            else:
                console.print("\n[bold red]✗ Validation failed[/bold red]")
                if missing_tables:
                    console.print(f"  [red]• {len(missing_tables)} tables missing[/red]")
                if not fk_valid:
                    console.print(f"  [red]• Foreign key issues found[/red]")
                if not data_valid:
                    console.print(f"  [red]• Data issues found[/red]")
                console.print()
            
            return all_valid
            
    except ValueError as e:
        console.print(f"[bold red]✗ Configuration Error:[/bold red] {e}\n")
        logger.error(f"Validation configuration error: {e}")
        return False
        
    except Exception as e:
        console.print(f"[bold red]✗ Validation Failed:[/bold red] {e}\n")
        logger.error(f"Validation failed: {e}", exc_info=True)
        return False


def status_command(verbose: bool = False) -> None:
    """
    Show table creation status overview.
    
    Args:
        verbose: Enable verbose output
    """
    console.print("\n[bold]Table Creation Status[/bold]\n")
    
    try:
        platform = get_dwh_platform()
        connector = get_connector(platform)
        schema_manager = SchemaManager()

        with connector:
            is_snowflake = platform in ("sf", "snowflake")
            is_databricks = platform in ("db", "dbx", "databricks")
            is_bigquery = platform in ("bq", "bigquery")
            database = schema = None

            if is_snowflake:
                result = connector.execute_query(
                    "SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE(), CURRENT_ROLE()"
                )
                if result:
                    database, schema, warehouse, role = result[0]
                    tree = Tree("[bold]Snowflake Connection[/bold]")
                    tree.add(f"Database: [cyan]{database or 'Not set'}[/cyan]")
                    tree.add(f"Schema: [cyan]{schema or 'Not set'}[/cyan]")
                    tree.add(f"Warehouse: [cyan]{warehouse or 'Not set'}[/cyan]")
                    tree.add(f"Role: [cyan]{role or 'Not set'}[/cyan]")
                    console.print(tree)
                    console.print()
            elif is_databricks:
                result = connector.execute_query(
                    "SELECT current_catalog() AS cat, current_schema() AS sch"
                )
                if result:
                    database, schema = result[0]
                    tree = Tree("[bold]Databricks Connection[/bold]")
                    tree.add(f"Catalog: [cyan]{database or 'Not set'}[/cyan]")
                    tree.add(f"Schema: [cyan]{schema or 'Not set'}[/cyan]")
                    console.print(tree)
                    console.print()
            elif is_bigquery:
                database = connector.project
                schema = connector.dataset
                tree = Tree("[bold]BigQuery Connection[/bold]")
                tree.add(f"Project: [cyan]{database or 'Not set'}[/cyan]")
                tree.add(f"Dataset: [cyan]{schema or 'Not set'}[/cyan]")
                tree.add(f"Location: [cyan]{connector.location or 'Not set'}[/cyan]")
                console.print(tree)
                console.print()
            elif is_redshift:
                result = connector.execute_query(
                    "SELECT current_database() AS db, current_schema() AS sch"
                )
                if result:
                    database, schema = result[0]
                    tree = Tree("[bold]Redshift Connection[/bold]")
                    tree.add(f"Database: [cyan]{database or 'Not set'}[/cyan]")
                    tree.add(f"Schema: [cyan]{schema or 'Not set'}[/cyan]")
                    console.print(tree)
                    console.print()
            else:
                result = connector.execute_query(
                    "SELECT current_database() AS db, current_schema() AS sch"
                )
                if result:
                    database, schema = result[0]
                    tree = Tree("[bold]PostgreSQL Connection[/bold]")
                    tree.add(f"Database: [cyan]{database or 'Not set'}[/cyan]")
                    tree.add(f"Schema: [cyan]{schema or 'Not set'}[/cyan]")
                    console.print(tree)
                    console.print()

            # Get table counts
            if database and schema:
                if is_snowflake:
                    tables_query = f"""
                        SELECT
                            COUNT(*) as table_count,
                            COALESCE(SUM(ROW_COUNT), 0) as total_rows,
                            COALESCE(SUM(BYTES), 0) as total_bytes
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_SCHEMA = UPPER('{schema}')
                    """
                    result = connector.execute_query(tables_query)
                    if result:
                        table_count, total_rows, total_bytes = result[0]
                    else:
                        table_count, total_rows, total_bytes = 0, 0, 0
                elif is_databricks:
                    count_query = f"""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_catalog = '{database}'
                          AND table_schema = '{schema}'
                          AND table_type = 'MANAGED'
                    """
                    count_result = connector.execute_query(count_query)
                    table_count = count_result[0][0] if count_result else 0
                    # Sum row counts across all expected tables; Databricks
                    # information_schema doesn't expose per-table row counts.
                    total_rows = 0
                    for tbl in [t.table_name for t in schema_manager.all_tables]:
                        try:
                            r = connector.execute_query(
                                f"SELECT COUNT(*) FROM {database}.{schema}.{tbl}"
                            )
                            total_rows += r[0][0] if r else 0
                        except Exception:
                            pass
                    total_bytes = None
                elif is_bigquery:
                    summary_query = f"""
                        SELECT COUNT(*) AS table_count,
                               COALESCE(SUM(row_count), 0) AS total_rows,
                               COALESCE(SUM(size_bytes), 0) AS total_bytes
                        FROM `{database}.{schema}.__TABLES__`
                    """
                    result = connector.execute_query(summary_query)
                    if result:
                        table_count, total_rows, total_bytes = result[0]
                    else:
                        table_count, total_rows, total_bytes = 0, 0, 0
                elif is_redshift:
                    count_query = f"""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = '{schema}'
                          AND table_type = 'BASE TABLE'
                    """
                    count_result = connector.execute_query(count_query)
                    table_count = count_result[0][0] if count_result else 0
                    total_rows = 0
                    for tbl in [t.table_name for t in schema_manager.all_tables]:
                        try:
                            r = connector.execute_query(
                                f'SELECT COUNT(*) FROM "{schema}"."{tbl}"'
                            )
                            total_rows += r[0][0] if r else 0
                        except Exception:
                            pass
                    total_bytes = None
                else:
                    count_query = f"""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = '{schema}'
                        AND table_type = 'BASE TABLE'
                    """
                    rows_query = f"""
                        SELECT COALESCE(SUM(n_live_tup), 0)
                        FROM pg_stat_user_tables
                        WHERE schemaname = '{schema}'
                    """
                    count_result = connector.execute_query(count_query)
                    rows_result = connector.execute_query(rows_query)
                    table_count = count_result[0][0] if count_result else 0
                    total_rows = rows_result[0][0] if rows_result else 0
                    total_bytes = None

                expected_tables = len(schema_manager.all_tables)

                status_table = Table(show_header=False, box=None)
                status_table.add_column("Metric", style="dim")
                status_table.add_column("Value", style="bold")

                status_table.add_row("Expected Tables", str(expected_tables))
                status_table.add_row("Deployed Tables", str(table_count))
                status_table.add_row("Total Rows", f"{total_rows:,}")
                if total_bytes is not None:
                    status_table.add_row("Total Size", format_bytes(total_bytes))

                completion = (table_count / expected_tables * 100) if expected_tables > 0 else 0
                status_table.add_row("Completion", f"{completion:.0f}%")

                console.print(Panel(status_table, title="Deployment Status", border_style="blue"))
            
    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]\n")
        logger.error(f"Status check failed: {e}")


def check_foreign_keys(
    connector: BaseConnector,
    schema: str,
    platform: str,
    verbose: bool = False,
    database: Optional[str] = None,
) -> bool:
    """
    Check foreign key constraints.

    Uses platform-specific queries:
    - Snowflake: INFORMATION_SCHEMA with UPPER() and REFERENTIAL_CONSTRAINTS
    - PostgreSQL: information_schema with pg_catalog for referenced table lookup
    - Databricks: information_schema with explicit table_catalog filter (UC)

    Args:
        connector: DWH connector
        schema: Schema name
        platform: DWH platform identifier (e.g. "sf", "pg", "dbx")
        verbose: Enable verbose output
        database: Catalog/database name (required for Databricks 3-part naming)

    Returns:
        True if all FKs are valid
    """
    is_snowflake = platform in ("sf", "snowflake")
    is_databricks = platform in ("db", "dbx", "databricks")
    is_bigquery = platform in ("bq", "bigquery")

    if is_snowflake:
        fk_query = f"""
            SELECT
                tc.TABLE_NAME,
                tc.CONSTRAINT_NAME,
                kcu.COLUMN_NAME,
                rc.TABLE_NAME as REFERENCED_TABLE
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            LEFT JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            WHERE tc.TABLE_SCHEMA = UPPER('{schema}')
            AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
            ORDER BY tc.TABLE_NAME
        """
    elif is_databricks:
        fk_query = f"""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS referenced_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_catalog = kcu.constraint_catalog
                AND tc.constraint_schema = kcu.constraint_schema
                AND tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_catalog = rc.constraint_catalog
                AND tc.constraint_schema = rc.constraint_schema
                AND tc.constraint_name = rc.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON rc.unique_constraint_catalog = ccu.constraint_catalog
                AND rc.unique_constraint_schema = ccu.constraint_schema
                AND rc.unique_constraint_name = ccu.constraint_name
            WHERE tc.table_catalog = '{database}'
              AND tc.table_schema = '{schema}'
              AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """
    elif is_bigquery:
        # BigQuery INFORMATION_SCHEMA is dataset-qualified: `project.dataset.INFORMATION_SCHEMA.X`.
        fk_query = f"""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS referenced_table
            FROM `{database}.{schema}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS` tc
            JOIN `{database}.{schema}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE` kcu
                ON tc.constraint_name = kcu.constraint_name
            LEFT JOIN `{database}.{schema}.INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE` ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """
    else:
        fk_query = f"""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS referenced_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rcon
                ON tc.constraint_name = rcon.constraint_name
                AND tc.table_schema = rcon.constraint_schema
            JOIN information_schema.constraint_column_usage ccu
                ON rcon.unique_constraint_name = ccu.constraint_name
                AND rcon.unique_constraint_schema = ccu.constraint_schema
            WHERE tc.table_schema = '{schema}'
            AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """
    
    try:
        result = connector.execute_query(fk_query)
        
        if not result:
            console.print("[yellow]No foreign key constraints found[/yellow]")
            return True
        
        table = Table(title="Foreign Key Constraints", show_header=True)
        table.add_column("Table", style="cyan")
        table.add_column("Constraint", style="white")
        table.add_column("Column")
        table.add_column("References")
        
        for row in result:
            table_name, constraint_name, column, ref_table = row
            table.add_row(table_name, constraint_name, column, ref_table or "N/A")
        
        console.print(table)
        console.print(f"\n[green]✓ {len(result)} foreign key constraints found[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error checking foreign keys: {e}[/red]")
        return False


def check_table_data(
    connector: BaseConnector,
    schema: str,
    tables: list,
    database: Optional[str] = None,
    platform: Optional[str] = None,
) -> bool:
    """
    Check for data presence in tables.

    Args:
        connector: DWH connector
        schema: Schema name
        tables: List of table names to check
        database: Catalog/database (required for Databricks 3-part naming)
        platform: Platform identifier — drives qualified-name construction

    Returns:
        True if data check passes
    """
    is_databricks = platform in ("db", "dbx", "databricks")
    is_bigquery = platform in ("bq", "bigquery")

    def _qualify(tbl: str) -> str:
        if is_bigquery and database:
            return f"`{database}.{schema}.{tbl}`"
        if is_databricks and database:
            return f"{database}.{schema}.{tbl}"
        return f"{schema}.{tbl}"

    empty_tables = []
    populated_tables = []

    for table_name in tables:
        try:
            result = connector.execute_query(f"SELECT COUNT(*) FROM {_qualify(table_name)}")
            row_count = result[0][0] if result else 0
            
            if row_count == 0:
                empty_tables.append(table_name)
            else:
                populated_tables.append((table_name, row_count))
                
        except Exception as e:
            logger.warning(f"Could not check data for {table_name}: {e}")
            empty_tables.append(table_name)
    
    # Display results
    if populated_tables:
        table = Table(title="Tables with Data", show_header=True)
        table.add_column("Table", style="cyan")
        table.add_column("Row Count", justify="right")
        
        for table_name, count in populated_tables:
            table.add_row(table_name, f"{count:,}")
        
        console.print(table)
    
    console.print(f"\n  Populated tables: [green]{len(populated_tables)}[/green]")
    console.print(f"  Empty tables: [yellow]{len(empty_tables)}[/yellow]")
    
    return True  # Empty tables are OK for validation


def format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string."""
    if num_bytes is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    
    return f"{num_bytes:.1f} PB"
