"""
CLI command for creating tables in the configured database/schema.
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.connectors import get_connector
from src.cli.config import get_dwh_platform
from src.table_manager.create_tables import TableCreator

logger = get_logger(__name__)
console = Console()


def create_tables_command(
    skip_fk: bool = False,
    dry_run: bool = False,
    table_name: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """
    Create tables in the configured database/schema.
    
    Args:
        skip_fk: Skip foreign key constraints
        dry_run: Show what would be done without executing
        table_name: Optional specific table to create (e.g., 'dim_customers')
        verbose: Enable verbose output
        
    Returns:
        True if successful, False otherwise
    """
    # Validate table_name doesn't look like a flag (user forgot space)
    if table_name and table_name.startswith("-"):
        console.print(f"[bold red]✗ Invalid table name: '{table_name}'[/bold red]")
        console.print("[dim]Table names cannot start with '-'. Did you forget a space before an option?[/dim]\n")
        return False
    
    if table_name:
        console.print(f"\n[bold]Creating table: {table_name}[/bold]\n")
    else:
        console.print("\n[bold]Creating tables...[/bold]\n")
    
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        return dry_run_create(skip_fk, table_name)
    
    try:
        platform = get_dwh_platform()
        connector = get_connector(platform)
        
        with connector:
            creator = TableCreator(connector)
            
            # Verify connection first
            console.print("[bold]Step 1: Verifying connection...[/bold]")
            status = creator.verify_connection(table_filter=table_name)
            
            if not status.get("connection_ok"):
                console.print("[bold red]✗ Connection failed[/bold red]\n")
                return False
            
            console.print("[green]✓ Connection verified[/green]\n")
            
            # Check database and schema
            if not status.get("database_exists"):
                console.print(f"[bold red]✗ Database does not exist[/bold red]")
                console.print("[dim]Please create the database first[/dim]\n")
                return False
            
            if not status.get("schema_exists"):
                console.print(f"[bold red]✗ Schema does not exist[/bold red]")
                console.print("[dim]Please create the schema first[/dim]\n")
                return False
            
            # Check if specific table was not found in schema
            if status.get("table_not_found"):
                console.print(f"[bold red]✗ Table '{table_name}' not found in schema definition[/bold red]")
                console.print("[dim]Check the table name and try again[/dim]\n")
                return False
            
            # Show existing/missing tables
            existing = status.get("existing_tables", [])
            missing = status.get("missing_tables", [])
            
            if existing:
                console.print(f"[dim]Existing tables: {len(existing)}[/dim]")
            if missing:
                console.print(f"[dim]Tables to create: {len(missing)}[/dim]\n")
            
            # Create tables
            console.print("[bold]Step 2: Creating tables...[/bold]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                task = progress.add_task("Creating tables...", total=100)
                
                tables_success = creator.create_tables(table_filter=table_name)
                progress.update(task, completed=50)
                
                # Apply foreign keys unless skipped
                fk_success = True
                if not skip_fk:
                    progress.update(task, description="Applying foreign keys...")
                    fk_success = creator.apply_foreign_keys(table_filter=table_name)
                else:
                    console.print("[dim]Skipping foreign key constraints[/dim]")
                
                progress.update(task, completed=100)
            
            # Display results
            stats = creator.stats
            
            table = Table(title="Creation Results", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white", justify="right")
            table.add_column("Status", style="green")
            
            table.add_row(
                "Tables Created",
                str(stats["tables_created"]),
                "✓" if stats["tables_failed"] == 0 else "⚠"
            )
            table.add_row(
                "Tables Failed",
                str(stats["tables_failed"]),
                "✓" if stats["tables_failed"] == 0 else "✗"
            )
            
            if not skip_fk:
                table.add_row(
                    "Foreign Keys Applied",
                    str(stats["constraints_applied"]),
                    "✓" if stats["constraints_failed"] == 0 else "⚠"
                )
                table.add_row(
                    "Foreign Keys Failed",
                    str(stats["constraints_failed"]),
                    "✓" if stats["constraints_failed"] == 0 else "✗"
                )
            
            console.print(table)
            
            # Final status
            success = tables_success and (fk_success or skip_fk)
            
            if success:
                console.print("\n[bold green]✓ Table creation completed successfully![/bold green]\n")
            else:
                console.print("\n[bold red]✗ Table creation completed with errors[/bold red]")
                if stats["errors"]:
                    console.print("\n[bold]Errors:[/bold]")
                    for error in stats["errors"][:5]:
                        console.print(f"  [red]• {error}[/red]")
                console.print()
            
            logger.info(f"Creation complete: tables={stats['tables_created']}, fks={stats['constraints_applied']}")
            return success
            
    except ValueError as e:
        console.print(f"[bold red]✗ Configuration Error:[/bold red] {e}\n")
        console.print("[dim]Check your .env file or environment variables.[/dim]")
        logger.error(f"Configuration error: {e}")
        return False
        
    except Exception as e:
        console.print(f"[bold red]✗ Table Creation Failed:[/bold red] {e}\n")
        logger.error(f"Table creation failed: {e}", exc_info=True)
        return False


def dry_run_create(skip_fk: bool = False, table_name: Optional[str] = None) -> bool:
    """
    Show what would be created without making changes.
    
    Args:
        skip_fk: Skip foreign key constraints
        table_name: Optional specific table to show
        
    Returns:
        True always (dry run doesn't fail)
    """
    from src.sql_generator.schema_manager import SchemaManager
    
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
    
    console.print("[bold]Tables that would be created:[/bold]\n")
    
    table = Table(show_header=True)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Table Name", style="cyan")
    table.add_column("Type", style="magenta")
    
    for i, t in enumerate(tables_to_process, 1):
        if t.table_name.startswith("dim_"):
            table_type = "Dimension"
        elif t.table_name.startswith("fact_"):
            table_type = "Fact"
        else:
            table_type = "Bridge"
        table.add_row(str(i), t.table_name, table_type)
    
    console.print(table)
    
    if not skip_fk:
        fk_count = sum(len(t.foreign_keys) for t in tables_to_process if hasattr(t, 'foreign_keys'))
        console.print(f"\n[dim]Foreign keys that would be created: {fk_count}[/dim]")
    else:
        console.print("\n[dim]Foreign keys: SKIPPED[/dim]")
    
    console.print("\n[yellow]Run without --dry-run to execute[/yellow]\n")
    return True
