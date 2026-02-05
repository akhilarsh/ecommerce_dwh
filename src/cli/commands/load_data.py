"""
Load data into the data warehouse from CSV files.

Provides CLI interface for loading generated test data into Snowflake
or other supported data warehouse platforms.

Supports two modes:
- initial: Load from initial data generation output (paths.output_dir)
- incremental: Load from incremental data generation output (paths.incremental_output_dir)

Supports resume after partial failures:
- --resume: Continue from last state, skipping already loaded tables
- --clear-state: Clear saved state and start fresh
- --show-state: Display current load state without loading
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.data_generators import ReferentialIntegrityHandler, load_config

logger = get_logger(__name__)
console = Console()


def _resolve_input_dir(input_dir: Optional[str], mode: str) -> str:
    """
    Resolve input directory based on mode and explicit override.
    
    Args:
        input_dir: Explicit input directory override (None to use mode default)
        mode: Load mode ('initial' or 'incremental')
        
    Returns:
        Resolved input directory path
    """
    if input_dir is not None:
        return input_dir
    
    config = load_config()
    
    if mode == "initial":
        return config.paths.output_dir or "outputs/initial_data"
    elif mode == "incremental":
        base_dir = config.paths.incremental_output_dir or "outputs/incremental_data"
        # Check for date-ranged subdirectories (e.g., 2026-01-01_to_2026-01-31)
        base_path = Path(base_dir)
        if base_path.exists():
            subdirs = sorted([d for d in base_path.iterdir() if d.is_dir() and "_to_" in d.name])
            if subdirs:
                # Return most recent (last alphabetically = latest date range)
                return str(subdirs[-1])
        return base_dir
    else:
        return "outputs/initial_data"


def show_load_state() -> bool:
    """Display the current load state."""
    from src.data_loaders import LoadState
    
    state = LoadState.load()
    
    if not state:
        console.print("[yellow]No saved load state found.[/yellow]")
        return True
    
    console.print(f"\n[bold blue]Load State[/bold blue]\n")
    
    # Summary
    summary_table = Table(title="State Summary", show_header=True)
    summary_table.add_column("Property", style="cyan")
    summary_table.add_column("Value")
    
    summary_table.add_row("Mode", state.mode.capitalize())
    summary_table.add_row("Input Directory", state.input_dir)
    summary_table.add_row("Started At", state.started_at)
    summary_table.add_row("Completed At", state.completed_at or "In Progress")
    summary_table.add_row("Successful", str(len(state.successful_tables)))
    summary_table.add_row("Failed", str(len(state.failed_tables)))
    summary_table.add_row("Pending", str(len(state.pending_tables)))
    
    console.print(summary_table)
    console.print()
    
    # Tables detail
    if state.tables:
        detail_table = Table(title="Table Status", show_header=True)
        detail_table.add_column("Table", style="cyan")
        detail_table.add_column("Status")
        detail_table.add_column("Rows", justify="right")
        detail_table.add_column("Error")
        
        for name, tbl_state in state.tables.items():
            status_style = {
                "success": "[green]✓ Success[/green]",
                "failed": "[red]✗ Failed[/red]",
                "pending": "[yellow]○ Pending[/yellow]",
                "skipped": "[dim]- Skipped[/dim]",
            }.get(tbl_state.status, tbl_state.status)
            
            rows = f"{tbl_state.rows_loaded:,}" if tbl_state.rows_loaded else "-"
            error = tbl_state.error_message[:50] + "..." if tbl_state.error_message and len(tbl_state.error_message) > 50 else (tbl_state.error_message or "-")
            
            detail_table.add_row(name, status_style, rows, error)
        
        console.print(detail_table)
    
    # Hint
    if state.failed_tables:
        console.print(f"\n[dim]Run 'dwh load-data --resume' to retry {len(state.failed_tables)} failed table(s).[/dim]")
    
    return True


def clear_load_state() -> bool:
    """Clear the saved load state."""
    from src.data_loaders import LoadState
    
    state = LoadState.load()
    if state:
        LoadState.clear()
        console.print("[green]✓ Load state cleared.[/green]")
    else:
        console.print("[yellow]No load state to clear.[/yellow]")
    return True


def load_data_command(
    input_dir: Optional[str] = None,
    mode: str = "incremental",
    batch_size: int = 10000,
    truncate: bool = False,
    table_name: Optional[str] = None,
    platform: str = "snowflake",
    validate: bool = True,
    resume: bool = False,
    verbose: bool = False
) -> bool:
    """
    Load data into the data warehouse.
    
    Args:
        input_dir: Input directory for CSV data files (None = use mode default)
        mode: Load mode - 'initial' or 'incremental' (determines default input folder)
        batch_size: Batch size for loading
        truncate: Truncate tables before loading
        table_name: Optional specific table to load
        platform: Target platform (snowflake, redshift, bigquery, databricks)
        validate: Validate row counts after loading
        resume: Resume from last state, skipping already loaded tables
        verbose: Enable verbose output
        
    Returns:
        True if successful, False otherwise
    """
    from src.connectors.snowflake_connector import SnowflakeConnector
    from src.data_loaders import (
        DataLoadOrchestrator,
        LoaderConfig,
        LoadState,
        SnowflakeLoader,
    )
    
    # Resolve input directory from mode or explicit override
    resolved_input_dir = _resolve_input_dir(input_dir, mode)
    
    # Check resume state
    resume_info = ""
    if resume:
        existing_state = LoadState.load()
        if existing_state and existing_state.input_dir == resolved_input_dir:
            failed_count = len(existing_state.failed_tables)
            pending_count = len(existing_state.pending_tables)
            if failed_count > 0 or pending_count > 0:
                resume_info = f" (resuming: {failed_count} failed, {pending_count} pending)"
            else:
                console.print("[green]✓ All tables already loaded successfully.[/green]")
                console.print("[dim]Use --clear-state to reset and reload.[/dim]")
                return True
        else:
            resume = False  # No matching state, start fresh
    
    # Display header
    mode_display = mode.capitalize()
    if table_name:
        console.print(f"\n[bold blue]Loading Data ({mode_display}): {table_name}[/bold blue]\n")
    else:
        console.print(f"\n[bold blue]Loading {mode_display} Data into Snowflake{resume_info}[/bold blue]\n")
    
    # Check input directory
    input_path = Path(resolved_input_dir)
    
    if not input_path.exists():
        console.print(f"[red]✗ Input directory not found: {resolved_input_dir}[/red]")
        if mode == "initial":
            console.print("[dim]Run 'dwh generate-data' first to create initial data.[/dim]")
        else:
            console.print("[dim]Run 'dwh generate-data --mode incremental' first to create incremental data.[/dim]")
        return False
    
    # Find CSV files
    if table_name:
        csv_files = list(input_path.glob(f"{table_name}.csv"))
    else:
        csv_files = list(input_path.glob("*.csv"))
    
    if not csv_files:
        console.print(f"[red]✗ No CSV files found in {resolved_input_dir}[/red]")
        return False
    
    # Show files to load
    files_table = Table(title="Data Files to Load", show_header=True)
    files_table.add_column("File", style="cyan")
    files_table.add_column("Size", justify="right")
    
    for f in sorted(csv_files):
        files_table.add_row(f.name, format_bytes(f.stat().st_size))
    
    console.print(files_table)
    console.print()
    
    # Show configuration
    config_table = Table(title="Load Configuration", show_header=True)
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", justify="right")
    
    config_table.add_row("Mode", mode.capitalize())
    config_table.add_row("Input Directory", str(resolved_input_dir))
    config_table.add_row("Platform", platform)
    config_table.add_row("Batch Size", f"{batch_size:,}")
    config_table.add_row("Truncate Tables", "Yes" if truncate else "No")
    config_table.add_row("Validate After Load", "Yes" if validate else "No")
    config_table.add_row("Resume Mode", "Yes" if resume else "No")
    
    console.print(config_table)
    console.print()
    
    # Show load order
    handler = ReferentialIntegrityHandler()
    load_order = handler.get_load_order()
    available_tables = [f.stem for f in csv_files]
    tables_to_load = [t for t in load_order if t in available_tables]
    
    console.print("[bold]Load Order (FK dependencies):[/bold]")
    for i, tbl in enumerate(tables_to_load, 1):
        console.print(f"  {i:2}. {tbl}")
    console.print()
    
    # Create loader configuration
    loader_config = LoaderConfig(
        batch_size=batch_size,
        truncate_before_load=truncate,
        validate_after_load=validate,
        continue_on_error=False,
    )
    
    try:
        # Connect and load
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Connecting to Snowflake...", total=len(tables_to_load))
            
            with SnowflakeConnector() as connector:
                progress.update(task, description="Connected. Initializing loader...")
                
                # Create platform-specific loader
                if platform.lower() == "snowflake":
                    loader = SnowflakeLoader(connector, loader_config)
                else:
                    console.print(f"[red]✗ Platform '{platform}' not yet supported[/red]")
                    console.print("[dim]Currently supported: snowflake[/dim]")
                    return False
                
                # Create orchestrator
                orchestrator = DataLoadOrchestrator(loader, loader_config)
                
                # Set progress callback
                def update_progress(prog):
                    progress.update(
                        task,
                        completed=prog.loaded_tables,
                        description=f"Loading {prog.current_table}..."
                    )
                
                orchestrator.set_progress_callback(update_progress)
                
                # Load data
                tables_filter = [table_name] if table_name else None
                summary = orchestrator.load_from_csv_directory(
                    input_path,
                    tables=tables_filter,
                    resume=resume,
                    mode=mode
                )
                
                progress.update(task, completed=len(tables_to_load), description="Complete")
                
                # Verification - must be inside the connection context
                verification = None
                if validate and summary.all_successful:
                    verification = orchestrator.verify_load()
        
        console.print()
        
        # Show results
        results_table = Table(title="Load Results", show_header=True)
        results_table.add_column("Table", style="cyan")
        results_table.add_column("Rows", justify="right")
        results_table.add_column("Duration", justify="right")
        results_table.add_column("Status")
        
        for result in summary.results:
            status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            results_table.add_row(
                result.table_name,
                f"{result.rows_loaded:,}",
                f"{result.duration_seconds:.2f}s",
                status
            )
        
        console.print(results_table)
        
        # Summary
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Tables: {summary.successful_tables}/{summary.total_tables} successful")
        console.print(f"  Total rows: {summary.total_rows:,}")
        console.print(f"  Duration: {summary.total_duration:.2f}s")
        
        if summary.all_successful:
            console.print("\n[green]✓ Data loading completed successfully[/green]")
        else:
            console.print(f"\n[yellow]⚠ {summary.failed_tables} table(s) failed to load[/yellow]")
            for result in summary.get_failed_results():
                console.print(f"  [red]{result.table_name}: {result.errors}[/red]")
        
        # Show verification results (already fetched inside connection context)
        if verification is not None:
            console.print("\n[bold]Verifying loaded data...[/bold]")
            
            all_verified = True
            for tbl, info in verification.items():
                if tbl in [r.table_name for r in summary.results]:
                    if info.get("exists"):
                        if verbose:
                            console.print(f"  {tbl}: {info['actual']:,} rows")
                    else:
                        console.print(f"  [yellow]{tbl}: Table not found[/yellow]")
                        all_verified = False
            
            if all_verified:
                console.print("[green]✓ Verification passed[/green]")
        
        console.print()
        logger.info(f"Data loading complete: {summary.total_rows} rows in {summary.total_duration:.2f}s")
        return summary.all_successful
        
    except Exception as e:
        console.print(f"\n[red]✗ Error loading data: {e}[/red]")
        logger.error(f"Data loading failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


def format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string."""
    if num_bytes is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    
    return f"{num_bytes:.1f} PB"
