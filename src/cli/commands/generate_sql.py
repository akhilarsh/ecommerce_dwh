"""
SQL generation command for creating DDL/DML files.

Supports platform-specific output (Snowflake and PostgreSQL) written
to subdirectories: outputs/generated_sql/snowflake/ and outputs/generated_sql/pg/.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.sql_generator.schema_manager import SchemaManager

logger = get_logger(__name__)
console = Console()

PLATFORM_ALIASES = {
    "sf": "snowflake",
    "snowflake": "snowflake",
    "pg": "pg",
    "postgres": "pg",
    "postgresql": "pg",
    "db": "databricks",
    "dbx": "databricks",
    "databricks": "databricks",
}

PLATFORM_SUBDIRS = {
    "snowflake": "snowflake",
    "pg": "pg",
    "databricks": "databricks",
}


def generate_sql_command(
    output_dir: str = "outputs/generated_sql",
    include_drops: bool = False,
    table_name: Optional[str] = None,
    platform: Optional[str] = None,
    all_platforms: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Generate DDL/DML SQL files for all tables or a specific table.

    Writes platform-specific DDL to subdirectories (snowflake/, pg/).
    """
    if table_name:
        console.print(f"\n[bold]Generating SQL for table: {table_name}[/bold]\n")
    else:
        console.print("\n[bold]Generating SQL Files...[/bold]\n")

    try:
        output_path = Path(output_dir)
        schema_manager = SchemaManager()

        if table_name:
            matching_tables = [
                t for t in schema_manager.all_tables if t.table_name.lower() == table_name.lower()
            ]
            if not matching_tables:
                console.print(f"[bold red]✗ Table '{table_name}' not found[/bold red]")
                console.print("[dim]Available tables:[/dim]")
                for t in schema_manager.all_tables:
                    console.print(f"  • {t.table_name}")
                return False
            tables_to_process = matching_tables
        else:
            tables_to_process = schema_manager.all_tables

        platforms = _resolve_platforms(platform, all_platforms)
        all_files_generated: List[Tuple[str, str, str]] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for plat in platforms:
                subdir = PLATFORM_SUBDIRS[plat]
                plat_path = output_path / subdir
                plat_path.mkdir(parents=True, exist_ok=True)

                files = _generate_for_platform(
                    plat, plat_path, schema_manager, tables_to_process,
                    table_name, include_drops, progress,
                )
                all_files_generated.extend(files)

        table = Table(title="Generated SQL Files", show_header=True)
        table.add_column("Platform", style="magenta")
        table.add_column("File", style="cyan")
        table.add_column("Description", style="white")

        for plat_label, filename, description in all_files_generated:
            table.add_row(plat_label, filename, description)

        console.print(table)

        console.print(f"\n[bold green]✓ Generated {len(all_files_generated)} SQL files[/bold green]")
        console.print(f"[dim]Output directory: {output_path.absolute()}[/dim]\n")

        total_tables = len(tables_to_process)
        total_fks = sum(len(t.foreign_keys) for t in tables_to_process if hasattr(t, "foreign_keys"))
        console.print(f"  Tables: {total_tables}")
        console.print(f"  Foreign Keys: {total_fks}")
        console.print(f"  Platforms: {', '.join(platforms)}\n")

        logger.info(f"SQL generation complete: {len(all_files_generated)} files in {output_path}")
        return True

    except Exception as e:
        console.print(f"\n[bold red]✗ SQL Generation Failed:[/bold red] {e}\n")
        logger.error(f"SQL generation failed: {e}", exc_info=True)
        return False


def _resolve_platforms(platform: Optional[str], all_platforms: bool) -> List[str]:
    if all_platforms:
        return ["snowflake", "pg", "databricks"]

    if platform:
        normalized = PLATFORM_ALIASES.get(platform.lower())
        if not normalized:
            raise ValueError(
                f"Unknown platform '{platform}'. Supported: {', '.join(PLATFORM_ALIASES.keys())}"
            )
        return [normalized]

    try:
        from src.cli.config import get_dwh_platform
        active = get_dwh_platform()
        normalized = PLATFORM_ALIASES.get(active.lower())
        if normalized:
            return [normalized]
    except Exception:
        pass

    return ["snowflake"]


def _generate_for_platform(
    platform: str,
    plat_path: Path,
    schema_manager: SchemaManager,
    tables_to_process,
    table_name: Optional[str],
    include_drops: bool,
    progress: Progress,
) -> List[Tuple[str, str, str]]:
    """Generate DDL files for one platform, returning (platform_label, filename, description) tuples."""
    files_generated: List[Tuple[str, str, str]] = []
    labels = {"snowflake": "Snowflake", "pg": "PostgreSQL", "databricks": "Databricks"}
    label = labels.get(platform, platform)

    if platform == "snowflake":
        files_generated.extend(
            _generate_snowflake(plat_path, schema_manager, tables_to_process, table_name, include_drops, progress, label)
        )
    elif platform == "pg":
        files_generated.extend(
            _generate_pg(plat_path, schema_manager, tables_to_process, table_name, include_drops, progress, label)
        )
    elif platform == "databricks":
        files_generated.extend(
            _generate_dbx(plat_path, schema_manager, tables_to_process, table_name, include_drops, progress, label)
        )

    return files_generated


def _generate_snowflake(
    plat_path: Path,
    schema_manager: SchemaManager,
    tables_to_process,
    table_name: Optional[str],
    include_drops: bool,
    progress: Progress,
    label: str,
) -> List[Tuple[str, str, str]]:
    files: List[Tuple[str, str, str]] = []

    if include_drops:
        task = progress.add_task(f"[{label}] DROP statements...", total=None)
        if table_name:
            drop_file = plat_path / f"00_drop_{table_name}.sql"
            drop_scripts = [f"DROP TABLE IF EXISTS {t.table_name};" for t in tables_to_process]
        else:
            drop_file = plat_path / "00_drop_tables.sql"
            drop_scripts = schema_manager.get_drop_table_scripts()
        drop_file.write_text("\n\n".join(drop_scripts))
        files.append((label, drop_file.name, "DROP TABLE statements"))
        progress.remove_task(task)

    task = progress.add_task(f"[{label}] CREATE TABLE statements...", total=None)
    if table_name:
        create_file = plat_path / f"01_create_{table_name}.sql"
        create_scripts = [t.get_create_table_sql() for t in tables_to_process]
    else:
        create_file = plat_path / "01_create_tables.sql"
        create_scripts = schema_manager.get_create_table_scripts()
    create_file.write_text("\n\n".join(create_scripts))
    files.append((label, create_file.name, "CREATE TABLE statements"))
    progress.remove_task(task)

    task = progress.add_task(f"[{label}] Foreign keys...", total=None)
    if table_name:
        fk_scripts = []
        for t in tables_to_process:
            if hasattr(t, "foreign_keys") and t.foreign_keys:
                for fk in t.foreign_keys:
                    fk_scripts.append(fk.to_sql(t.get_full_table_name()))
        if fk_scripts:
            fk_file = plat_path / f"02_foreign_keys_{table_name}.sql"
            fk_file.write_text("\n\n".join(fk_scripts))
            files.append((label, fk_file.name, "Foreign key constraints"))
    else:
        fk_file = plat_path / "02_foreign_keys.sql"
        fk_scripts = schema_manager.get_foreign_key_scripts()
        fk_file.write_text("\n\n".join(fk_scripts) if fk_scripts else "-- No foreign keys defined")
        files.append((label, fk_file.name, "Foreign key constraints"))
    progress.remove_task(task)

    return files


def _generate_pg(
    plat_path: Path,
    schema_manager: SchemaManager,
    tables_to_process,
    table_name: Optional[str],
    include_drops: bool,
    progress: Progress,
    label: str,
) -> List[Tuple[str, str, str]]:
    import os
    from src.sql_generator.pg_ddl_adapter import (
        generate_pg_create_table,
        generate_pg_drop_table,
        generate_pg_foreign_keys,
    )

    pg_schema = os.getenv("POSTGRES_SCHEMA", "ecommerce_dwh")
    files: List[Tuple[str, str, str]] = []

    if include_drops:
        task = progress.add_task(f"[{label}] DROP statements...", total=None)
        drop_scripts = [generate_pg_drop_table(t, pg_schema) for t in reversed(list(tables_to_process))]
        if table_name:
            drop_file = plat_path / f"00_drop_{table_name}.sql"
        else:
            drop_file = plat_path / "00_drop_tables.sql"
        drop_file.write_text("\n\n".join(drop_scripts))
        files.append((label, drop_file.name, "DROP TABLE statements"))
        progress.remove_task(task)

    task = progress.add_task(f"[{label}] CREATE TABLE statements...", total=None)
    create_stmts: List[str] = []
    comment_stmts: List[str] = []

    for t in tables_to_process:
        create_sql, comments = generate_pg_create_table(t, pg_schema)
        create_stmts.append(create_sql)
        comment_stmts.extend(comments)

    if table_name:
        create_file = plat_path / f"01_create_{table_name}.sql"
    else:
        create_file = plat_path / "01_create_tables.sql"
    create_file.write_text("\n\n".join(create_stmts))
    files.append((label, create_file.name, "CREATE TABLE statements"))
    progress.remove_task(task)

    task = progress.add_task(f"[{label}] Foreign keys...", total=None)
    fk_scripts: List[str] = []
    for t in tables_to_process:
        fk_scripts.extend(generate_pg_foreign_keys(t, pg_schema))

    if fk_scripts:
        if table_name:
            fk_file = plat_path / f"02_foreign_keys_{table_name}.sql"
        else:
            fk_file = plat_path / "02_foreign_keys.sql"
        fk_file.write_text("\n\n".join(fk_scripts))
        files.append((label, fk_file.name, "Foreign key constraints"))
    progress.remove_task(task)

    if comment_stmts:
        task = progress.add_task(f"[{label}] Comments...", total=None)
        if table_name:
            comments_file = plat_path / f"03_comments_{table_name}.sql"
        else:
            comments_file = plat_path / "03_comments.sql"
        comments_file.write_text("\n".join(comment_stmts))
        files.append((label, comments_file.name, "COMMENT ON statements"))
        progress.remove_task(task)

    return files


def _generate_dbx(
    plat_path: Path,
    schema_manager: SchemaManager,
    tables_to_process,
    table_name: Optional[str],
    include_drops: bool,
    progress: Progress,
    label: str,
) -> List[Tuple[str, str, str]]:
    import os
    from src.sql_generator.dbx_ddl_adapter import (
        generate_dbx_create_schema,
        generate_dbx_create_table,
        generate_dbx_drop_table,
        generate_dbx_foreign_keys,
    )

    catalog = os.getenv("DATABRICKS_CATALOG", "main")
    schema = os.getenv("DATABRICKS_SCHEMA", "ecommerce_dwh")
    files: List[Tuple[str, str, str]] = []

    if include_drops:
        task = progress.add_task(f"[{label}] DROP statements...", total=None)
        drop_scripts = [
            generate_dbx_drop_table(t, catalog, schema)
            for t in reversed(list(tables_to_process))
        ]
        if table_name:
            drop_file = plat_path / f"00_drop_{table_name}.sql"
        else:
            drop_file = plat_path / "00_drop_tables.sql"
        drop_file.write_text("\n\n".join(drop_scripts))
        files.append((label, drop_file.name, "DROP TABLE statements"))
        progress.remove_task(task)

    task = progress.add_task(f"[{label}] CREATE TABLE statements...", total=None)
    create_stmts: List[str] = [generate_dbx_create_schema(catalog, schema)]
    for t in tables_to_process:
        create_sql, _ = generate_dbx_create_table(t, catalog, schema)
        create_stmts.append(create_sql)

    if table_name:
        create_file = plat_path / f"01_create_{table_name}.sql"
    else:
        create_file = plat_path / "01_create_tables.sql"
    create_file.write_text("\n\n".join(create_stmts))
    files.append((label, create_file.name, "CREATE TABLE statements"))
    progress.remove_task(task)

    task = progress.add_task(f"[{label}] Foreign keys...", total=None)
    fk_scripts: List[str] = []
    for t in tables_to_process:
        fk_scripts.extend(generate_dbx_foreign_keys(t, catalog, schema))

    if fk_scripts:
        if table_name:
            fk_file = plat_path / f"02_foreign_keys_{table_name}.sql"
        else:
            fk_file = plat_path / "02_foreign_keys.sql"
        fk_file.write_text("\n\n".join(fk_scripts))
        files.append((label, fk_file.name, "Foreign key constraints"))
    progress.remove_task(task)

    return files


def list_tables_command(verbose: bool = False) -> None:
    """List all table definitions."""
    console.print("\n[bold]Table Definitions[/bold]\n")

    schema_manager = SchemaManager()

    dimensions = [t for t in schema_manager.all_tables if t.table_name.startswith("dim_")]
    facts = [t for t in schema_manager.all_tables if t.table_name.startswith("fact_")]
    bridges = [t for t in schema_manager.all_tables if t.table_name.startswith("bridge_")]

    table = Table(title="E-Commerce Data Warehouse Tables", show_header=True)
    table.add_column("Table Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Columns", style="white", justify="right")
    table.add_column("Foreign Keys", style="yellow", justify="right")

    for t in dimensions:
        fk_count = len(t.foreign_keys) if hasattr(t, "foreign_keys") else 0
        table.add_row(t.table_name, "Dimension", str(len(t.columns)), str(fk_count))

    for t in facts:
        fk_count = len(t.foreign_keys) if hasattr(t, "foreign_keys") else 0
        table.add_row(t.table_name, "Fact", str(len(t.columns)), str(fk_count))

    for t in bridges:
        fk_count = len(t.foreign_keys) if hasattr(t, "foreign_keys") else 0
        table.add_row(t.table_name, "Bridge", str(len(t.columns)), str(fk_count))

    console.print(table)
    console.print(f"\n[dim]Total: {len(dimensions)} dimensions, {len(facts)} facts, {len(bridges)} bridges[/dim]\n")
