"""
SQL generation command for creating DDL/DML files.
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.sql_generator.schema_manager import SchemaManager
from src.sql_generator.ddl_generator import DDLGenerator
from src.sql_generator.constraint_generator import ConstraintGenerator

logger = get_logger(__name__)
console = Console()


def generate_sql_command(
    output_dir: str = "outputs/generated_sql",
    include_drops: bool = False,
    table_name: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """
    Generate DDL/DML SQL files for all tables or a specific table.
    
    Args:
        output_dir: Output directory for SQL files
        include_drops: Include DROP TABLE statements
        table_name: Optional specific table to generate (e.g., 'dim_customers')
        verbose: Enable verbose output
        
    Returns:
        True if successful, False otherwise
    """
    if table_name:
        console.print(f"\n[bold]Generating SQL for table: {table_name}[/bold]\n")
    else:
        console.print("\n[bold]Generating SQL Files...[/bold]\n")
    
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema manager
        schema_manager = SchemaManager()
        
        # Filter tables if specific table requested
        if table_name:
            matching_tables = [t for t in schema_manager.all_tables if t.table_name.lower() == table_name.lower()]
            if not matching_tables:
                console.print(f"[bold red]✗ Table '{table_name}' not found[/bold red]")
                console.print("[dim]Available tables:[/dim]")
                for t in schema_manager.all_tables:
                    console.print(f"  • {t.table_name}")
                return False
            tables_to_process = matching_tables
        else:
            tables_to_process = schema_manager.all_tables
        
        files_generated = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Generate DROP statements if requested
            if include_drops:
                task = progress.add_task("Generating DROP statements...", total=None)
                if table_name:
                    drop_file = output_path / f"00_drop_{table_name}.sql"
                    drop_scripts = [f"DROP TABLE IF EXISTS {t.table_name};" for t in tables_to_process]
                else:
                    drop_file = output_path / "00_drop_tables.sql"
                    drop_scripts = schema_manager.get_drop_table_scripts()
                drop_sql = "\n\n".join(drop_scripts)
                drop_file.write_text(drop_sql)
                files_generated.append((drop_file.name, "DROP TABLE statements"))
                progress.remove_task(task)
            
            # Generate CREATE TABLE statements
            task = progress.add_task("Generating CREATE TABLE statements...", total=None)
            if table_name:
                create_file = output_path / f"01_create_{table_name}.sql"
                create_scripts = [t.get_create_table_sql() for t in tables_to_process]
            else:
                create_file = output_path / "01_create_tables.sql"
                create_scripts = schema_manager.get_create_table_scripts()
            create_sql = "\n\n".join(create_scripts)
            create_file.write_text(create_sql)
            files_generated.append((create_file.name, "CREATE TABLE statements"))
            progress.remove_task(task)
            
            # Generate foreign key constraints (only if table has FKs)
            task = progress.add_task("Generating foreign key constraints...", total=None)
            if table_name:
                fk_scripts = []
                for t in tables_to_process:
                    if hasattr(t, 'foreign_keys') and t.foreign_keys:
                        for fk in t.foreign_keys:
                            fk_scripts.append(fk.to_sql(t.get_full_table_name()))
                # Only create FK file if there are foreign keys
                if fk_scripts:
                    fk_file = output_path / f"02_foreign_keys_{table_name}.sql"
                    fk_sql = "\n\n".join(fk_scripts)
                    fk_file.write_text(fk_sql)
                    files_generated.append((fk_file.name, "Foreign key constraints"))
            else:
                fk_file = output_path / "02_foreign_keys.sql"
                fk_scripts = schema_manager.get_foreign_key_scripts()
                fk_sql = "\n\n".join(fk_scripts) if fk_scripts else "-- No foreign keys defined"
                fk_file.write_text(fk_sql)
                files_generated.append((fk_file.name, "Foreign key constraints"))
            progress.remove_task(task)
        
        # Display results
        table = Table(title="Generated SQL Files", show_header=True)
        table.add_column("File", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Path", style="dim")
        
        for filename, description in files_generated:
            table.add_row(filename, description, str(output_path / filename))
        
        console.print(table)
        
        # Summary
        console.print(f"\n[bold green]✓ Generated {len(files_generated)} SQL files[/bold green]")
        console.print(f"[dim]Output directory: {output_path.absolute()}[/dim]\n")
        
        # Table summary
        total_tables = len(tables_to_process)
        total_fks = sum(len(t.foreign_keys) for t in tables_to_process if hasattr(t, 'foreign_keys'))
        
        console.print(f"  Tables: {total_tables}")
        console.print(f"  Foreign Keys: {total_fks}")
        
        logger.info(f"SQL generation complete: {len(files_generated)} files in {output_path}")
        return True
        
    except Exception as e:
        console.print(f"\n[bold red]✗ SQL Generation Failed:[/bold red] {e}\n")
        logger.error(f"SQL generation failed: {e}", exc_info=True)
        return False


def list_tables_command(verbose: bool = False) -> None:
    """
    List all table definitions.
    
    Args:
        verbose: Enable verbose output
    """
    console.print("\n[bold]Table Definitions[/bold]\n")
    
    schema_manager = SchemaManager()
    
    # Group tables by type
    dimensions = [t for t in schema_manager.all_tables if t.table_name.startswith("dim_")]
    facts = [t for t in schema_manager.all_tables if t.table_name.startswith("fact_")]
    bridges = [t for t in schema_manager.all_tables if t.table_name.startswith("bridge_")]
    
    table = Table(title="E-Commerce Data Warehouse Tables", show_header=True)
    table.add_column("Table Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Columns", style="white", justify="right")
    table.add_column("Foreign Keys", style="yellow", justify="right")
    
    for t in dimensions:
        fk_count = len(t.foreign_keys) if hasattr(t, 'foreign_keys') else 0
        table.add_row(t.table_name, "Dimension", str(len(t.columns)), str(fk_count))
    
    for t in facts:
        fk_count = len(t.foreign_keys) if hasattr(t, 'foreign_keys') else 0
        table.add_row(t.table_name, "Fact", str(len(t.columns)), str(fk_count))
    
    for t in bridges:
        fk_count = len(t.foreign_keys) if hasattr(t, 'foreign_keys') else 0
        table.add_row(t.table_name, "Bridge", str(len(t.columns)), str(fk_count))
    
    console.print(table)
    
    console.print(f"\n[dim]Total: {len(dimensions)} dimensions, {len(facts)} facts, {len(bridges)} bridges[/dim]\n")
