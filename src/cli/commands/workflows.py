"""
CLI commands for execution workflows.

Provides commands for:
- setup-tables: One-time table creation
- create-and-load: Full deployment (fresh with --drop-existing, or incremental for new tables)
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.workflows import WorkflowResult

logger = get_logger(__name__)
console = Console()


def setup_tables_command(
    database: Optional[str] = None,
    schema: Optional[str] = None,
    drop_existing: bool = False,
    dry_run: bool = False,
    skip_fk: bool = False,
    views_only: bool = False,
    verbose: bool = False,
    return_result: bool = False
) -> Union[bool, Tuple[bool, Optional[WorkflowResult]]]:
    """
    Execute table setup workflow.
    
    Args:
        database: Target database (uses env var if not provided)
        schema: Target schema (uses env var if not provided)
        drop_existing: Drop existing tables before creation
        dry_run: Show what would be done without executing
        skip_fk: Skip foreign key constraints
        verbose: Enable verbose output
        return_result: If True, return (success, WorkflowResult) tuple
        
    Returns:
        True if successful (or tuple if return_result=True)
    """
    from src.workflows import TableSetupWorkflow, TableSetupConfig
    
    console.print("\n[bold]Table Setup Workflow[/bold]\n")

    if views_only:
        from src.connectors import get_connector
        from src.cli.config import get_dwh_platform
        from src.workflows.table_setup_workflow import TableSetupWorkflow
        platform = get_dwh_platform()
        workflow = TableSetupWorkflow()
        with get_connector(platform) as connector:
            import os
            schema_name = schema or os.getenv("POSTGRES_SCHEMA") or os.getenv("SNOWFLAKE_SCHEMA", "public")
            views_result = workflow._create_views(connector, platform, schema_name)
        views_created = views_result["created"]
        views_failed = views_result["failed"]
        if views_created:
            console.print(f"[green]✓ Views created: {views_created}[/green]")
        if views_failed:
            console.print(f"[yellow]⚠ {views_failed} view(s) failed:[/yellow]")
            for err in views_result["errors"]:
                console.print(f"  [red]• {err}[/red]")
        success = views_failed == 0
        if return_result:
            return success, None
        return success

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

    if drop_existing:
        console.print("[yellow]WARNING: Existing tables will be dropped![/yellow]\n")
    
    config = TableSetupConfig(
        database=database,
        schema=schema,
        drop_existing=drop_existing,
        dry_run=dry_run,
        apply_foreign_keys=not skip_fk
    )
    
    console.print(f"[dim]Database: {database or '(from environment)'}[/dim]")
    console.print(f"[dim]Schema: {schema or '(from environment)'}[/dim]")
    console.print(f"[dim]Drop existing: {drop_existing}[/dim]")
    console.print(f"[dim]Apply FKs: {not skip_fk}[/dim]\n")
    
    workflow = TableSetupWorkflow()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Running table setup workflow...", total=None)
        result = workflow.run(config)
    
    # Display results
    _display_workflow_result(result)
    
    if result.success:
        console.print("[bold green]✓ Table setup completed successfully![/bold green]\n")

        # Show details
        if result.details.get("tables_created"):
            console.print(f"[dim]Tables created: {result.details['tables_created']}[/dim]")
        if result.details.get("fks_applied"):
            console.print(f"[dim]Foreign keys applied: {result.details['fks_applied']}[/dim]")

        # Show view results
        views_created = result.details.get("views_created", 0)
        views_failed = result.details.get("views_failed", 0)
        if views_created:
            console.print(f"[dim]Views created: {views_created}[/dim]")
        if views_failed:
            console.print(f"[yellow]⚠ {views_failed} view(s) failed to create:[/yellow]")
            for err in result.details.get("views_errors", []):
                console.print(f"  [red]• {err}[/red]")
    else:
        console.print(f"[bold red]✗ Table setup failed: {result.error}[/bold red]\n")
    
    if return_result:
        return result.success, result
    return result.success


def create_and_load_command(
    drop_existing: bool = False,
    skip_fk: bool = False,
    skip_load: bool = False,
    customers: Optional[int] = None,
    products: Optional[int] = None,
    orders: Optional[int] = None,
    stores: Optional[int] = None,
    employees: Optional[int] = None,
    seed: Optional[int] = None,
    verbose: bool = False
) -> bool:
    """
    Execute deployment: create tables + generate data + load.
    
    Behavior depends on --drop-existing flag:
    
    With --drop-existing (fresh deployment):
        1. Drop all existing tables
        2. Create all tables
        3. Generate all data
        4. Load all data (truncate)
    
    Without --drop-existing (incremental):
        1. Skip existing tables, create only new tables
        2. If new tables created: generate all data (for FK integrity), load only new tables
        3. If no new tables: exit early (nothing to do)
    
    Args:
        drop_existing: Drop existing tables before creation (fresh deployment)
        skip_fk: Skip foreign key constraints
        skip_load: Only create tables, skip data generation and loading
        customers: Override number of customers (from config if not provided)
        products: Override number of products (from config if not provided)
        orders: Override number of orders/sales (from config if not provided)
        stores: Override number of stores (from config if not provided)
        employees: Override number of employees (from config if not provided)
        seed: Override random seed (from config if not provided)
        verbose: Enable verbose output
        
    Returns:
        True if successful
    """
    from src.cli.commands.generate_data import generate_initial_command
    from src.cli.commands.load_data import load_data_command
    
    mode_label = "Fresh Deployment" if drop_existing else "Incremental Deployment"
    
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print(f"[bold blue]           CREATE AND LOAD - {mode_label}[/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]\n")
    
    if drop_existing:
        console.print("[yellow]Mode: Fresh deployment (drop + create + load all)[/yellow]\n")
    else:
        console.print("[yellow]Mode: Incremental (create new tables + load new only)[/yellow]\n")
    
    # Step 1: Create tables
    step1_desc = "Dropping and creating tables..." if drop_existing else "Creating new tables (existing skipped)..."
    console.print(f"[bold cyan]Step 1/3: {step1_desc}[/bold cyan]\n")
    
    tables_success, result = setup_tables_command(
        drop_existing=drop_existing,
        skip_fk=skip_fk,
        verbose=verbose,
        return_result=True
    )
    
    if not tables_success:
        console.print("[bold red]✗ Table creation failed. Aborting.[/bold red]\n")
        return False
    
    if skip_load:
        console.print("[yellow]Skipping data generation and load (--skip-load)[/yellow]\n")
        console.print("[bold green]✓ Create-and-load completed (tables only)[/bold green]\n")
        return True
    
    # Get list of newly created tables
    new_tables: List[str] = result.details.get("new_tables_created", []) if result else []
    
    # For incremental mode, check if there are new tables to load
    if not drop_existing:
        if not new_tables:
            console.print("[yellow]No new tables were created.[/yellow]")
            console.print("[dim]All tables already exist. Use --drop-existing to recreate and reload.[/dim]\n")
            console.print("[bold green]✓ Create-and-load completed (no changes needed)[/bold green]\n")
            return True
        console.print(f"[green]New tables created: {', '.join(new_tables)}[/green]\n")
    
    # Step 2: Generate initial data (all tables for FK referential integrity)
    console.print("\n[bold cyan]Step 2/3: Generating data (all tables for FK integrity)...[/bold cyan]\n")
    
    generate_success = generate_initial_command(
        customers=customers,
        products=products,
        orders=orders,
        stores=stores,
        employees=employees,
        seed=seed,
        validate=True,
        verbose=verbose
    )
    
    if not generate_success:
        console.print("[bold red]✗ Data generation failed. Aborting.[/bold red]\n")
        return False
    
    # Step 3: Load data
    if drop_existing:
        # Fresh deployment: load all tables
        console.print("\n[bold cyan]Step 3/3: Loading data into warehouse...[/bold cyan]\n")
        
        load_success = load_data_command(
            mode="initial",
            truncate=True,
            validate=True,
            verbose=verbose
        )
        
        if not load_success:
            console.print("[bold red]✗ Data load failed.[/bold red]\n")
            return False
    else:
        # Incremental: load only new tables (in FK dependency order)
        console.print(f"\n[bold cyan]Step 3/3: Loading data for new tables only...[/bold cyan]\n")
        
        # Sort new tables by FK dependency order (dimensions before facts)
        from src.sql_generator.schema_manager import SchemaManager
        schema_manager = SchemaManager()
        all_tables_ordered = [t.table_name.lower() for t in schema_manager.all_tables]
        
        # Filter to only new tables, preserving FK order
        new_tables_lower = {t.lower() for t in new_tables}
        new_tables_ordered = [t for t in all_tables_ordered if t in new_tables_lower]
        
        console.print(f"[dim]Tables to load (FK order): {', '.join(new_tables_ordered)}[/dim]\n")
        
        # Check which tables have generated CSV files
        from src.data_generators.config import load_config
        cfg = load_config()
        data_dir = Path(cfg.paths.output_dir)
        
        all_loaded = True
        for table_name in new_tables_ordered:
            csv_file = data_dir / f"{table_name}.csv"
            if not csv_file.exists():
                console.print(f"[yellow]⊘ No data file for {table_name}, skipping load[/yellow]")
                continue
                
            console.print(f"[dim]Loading {table_name}...[/dim]")
            load_success = load_data_command(
                mode="initial",
                truncate=True,  # Safe - these are new empty tables
                table_name=table_name,
                validate=True,
                verbose=verbose
            )
            if not load_success:
                console.print(f"[red]✗ Failed to load {table_name}[/red]")
                all_loaded = False
            else:
                console.print(f"[green]✓ Loaded {table_name}[/green]")
        
        if not all_loaded:
            console.print("\n[bold yellow]⚠ Some tables failed to load[/bold yellow]\n")
            return False
    
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold green]✓ CREATE AND LOAD COMPLETED SUCCESSFULLY[/bold green]")
    if not drop_existing and new_tables:
        console.print(f"[dim]New tables loaded: {', '.join(new_tables)}[/dim]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]\n")
    
    return True


def generate_and_load_command(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    new_customers: Optional[int] = None,
    new_orders: Optional[int] = None,
    new_interactions: Optional[int] = None,
    new_loyalty: Optional[int] = None,
    seed: Optional[int] = None,
    truncate: bool = False,
    validate: bool = True,
    verbose: bool = False
) -> bool:
    """
    Generate incremental data and load it into the warehouse.
    
    Combines generate-incremental + load-data into a single workflow.
    Uses dates from config or CLI overrides.
    
    Args:
        start_date: Start date YYYY-MM-DD (from config if not provided)
        end_date: End date YYYY-MM-DD (from config if not provided)
        new_customers: Number of new customers (from config if not provided)
        new_orders: Number of new orders (from config if not provided)
        new_interactions: Number of new interactions (from config if not provided)
        new_loyalty: Number of new loyalty transactions (from config if not provided)
        seed: Random seed (from config if not provided)
        truncate: Truncate tables before loading
        validate: Validate referential integrity
        verbose: Enable verbose output
        
    Returns:
        True if successful
    """
    from src.cli.commands.generate_data import generate_incremental_command
    from src.cli.commands.load_data import load_data_command
    from src.data_generators.config import load_config
    from datetime import datetime, date
    
    # Load config to get dates for display
    cfg = load_config()
    
    # Parse dates
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start = cfg.incremental.start_date or date.today()
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end = cfg.incremental.end_date or date.today()
    
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]              GENERATE AND LOAD INCREMENTAL DATA[/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]\n")
    
    console.print(f"[dim]Date range: {start} to {end}[/dim]\n")
    
    # Step 1: Generate incremental data
    console.print("[bold cyan]Step 1/2: Generating incremental data...[/bold cyan]\n")
    
    generate_success = generate_incremental_command(
        start_date=start_date,
        end_date=end_date,
        new_customers=new_customers,
        new_orders=new_orders,
        new_interactions=new_interactions,
        new_loyalty=new_loyalty,
        seed=seed,
        validate=validate,
        verbose=verbose
    )
    
    if not generate_success:
        console.print("[bold red]✗ Data generation failed. Aborting.[/bold red]\n")
        return False
    
    # Step 2: Load the generated data
    console.print("\n[bold cyan]Step 2/2: Loading data into warehouse...[/bold cyan]\n")
    
    # The generated data is in a date-ranged folder - load_data will auto-detect the latest
    load_success = load_data_command(
        mode="incremental",
        truncate=truncate,
        validate=validate,
        verbose=verbose
    )
    
    if not load_success:
        console.print("[bold red]✗ Data load failed.[/bold red]\n")
        return False
    
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold green]✓ GENERATE AND LOAD COMPLETED SUCCESSFULLY[/bold green]")
    console.print(f"[dim]Date range: {start} to {end}[/dim]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]\n")
    
    return True


def _display_workflow_result(result: "WorkflowResult") -> None:
    """Display workflow result summary."""
    table = Table(title="Workflow Result", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Workflow", result.workflow_name)
    table.add_row("Status", "[green]SUCCESS[/green]" if result.success else "[red]FAILED[/red]")
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    table.add_row("Stages Completed", str(len(result.stages_completed)))
    
    if result.error:
        table.add_row("Error", f"[red]{result.error}[/red]")
    
    console.print(table)
    console.print()
    
    # Show stages
    if result.stages_completed:
        console.print("[dim]Stages:[/dim]")
        for stage in result.stages_completed:
            console.print(f"  [green]✓[/green] {stage}")
        console.print()
