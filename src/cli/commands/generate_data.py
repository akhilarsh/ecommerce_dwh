"""
Data generation CLI command implementations for E-Commerce Data Warehouse.

Commands (aligned with helper structure):
- generate_initial_command: Bulk generation for fresh warehouse setup (all helpers)
- generate_incremental_command: Incremental data across date range (SalesHelper)
- generate_inventory_command: Periodic inventory snapshots (InventoryHelper)
- generate_store_command: Event-driven store opening (StoreHelper)
- generate_promotion_command: Event-driven promotion campaigns (CatalogHelper)
- cache_keys_command: Cache existing keys from Snowflake (utility)

Configuration sources (priority order):
1. CLI arguments (highest priority)
2. Environment variables (DATAGEN_* prefix)
3. YAML config file (datagen_config.yaml at project root)
"""

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.data_generators import (
    DataGenerator,
    DataGenConfig,
    GeneratorConfig,
    ExistingKeysLoader,
    ReferentialIntegrityHandler,
    load_config,
)

logger = get_logger(__name__)
console = Console()


# =============================================================================
# INITIAL LOAD MODE
# =============================================================================

def generate_initial_command(
    customers: Optional[int] = None,
    products: Optional[int] = None,
    orders: Optional[int] = None,
    stores: Optional[int] = None,
    employees: Optional[int] = None,
    promotions: Optional[int] = None,
    output_dir: Optional[str] = None,
    seed: Optional[int] = None,
    validate: bool = True,
    verbose: bool = False
) -> bool:
    """
    Generate complete initial load data for all tables.
    
    All parameters default to values from environment variables (DATAGEN_* prefix).
    CLI arguments override environment values.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load defaults from config (YAML + env vars)
        cfg = load_config()
        
        # Override config with CLI args if provided
        if customers is not None:
            cfg.volumes.customers = customers
        if products is not None:
            cfg.volumes.products = products
        if orders is not None:
            cfg.volumes.sales = orders
        if stores is not None:
            cfg.volumes.stores = stores
        if employees is not None:
            cfg.volumes.employees = employees
        if promotions is not None:
            cfg.volumes.promotions = promotions
        if output_dir is not None:
            cfg.paths.output_dir = output_dir
        if seed is not None:
            cfg.settings.seed = seed
        
        console.print("\n[bold blue]Generating Initial Load Data[/bold blue]\n")
        
        # Show configuration
        _show_initial_config(cfg)
        
        # Create generator
        gen = DataGenerator(config=cfg)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Generating data...", total=100)
            progress.update(task, description="Generating dimension tables...")
            result = gen.generate_initial(validate=validate)
            progress.update(task, completed=100)
        
        console.print()
        
        # Show results
        _show_generation_results(result, validate, verbose)
        
        # Save to CSV
        out_dir = cfg.paths.output_dir
        console.print(f"\n[bold]Saving to: {Path(out_dir).absolute()}[/bold]")
        file_paths = gen.save_to_csv(result, out_dir)
        console.print(f"[green]✓ Saved {len(file_paths)} CSV files[/green]")
        
        # Save keys cache for incremental
        cache_path = cfg.paths.keys_cache
        gen.save_keys_to_cache(cache_path)
        console.print(f"[dim]Saved keys cache: {cache_path}[/dim]")

        # Refresh cache from warehouse
        console.print("[dim]Refreshing keys cache from warehouse...[/dim]")
        cache_keys_command(output_file=cache_path, verbose=verbose)

        console.print()
        logger.info(f"Initial load complete: {result.total_records} records")
        return True
        
    except Exception as e:
        console.print(f"\n[red]✗ Error generating data: {e}[/red]")
        logger.error(f"Data generation failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# INCREMENTAL MODE
# =============================================================================

def generate_incremental_command(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    new_customers: Optional[int] = None,
    new_accounts: Optional[int] = None,
    new_orders: Optional[int] = None,
    new_interactions: Optional[int] = None,
    new_loyalty: Optional[int] = None,
    output_dir: Optional[str] = None,
    keys_cache: Optional[str] = None,
    seed: Optional[int] = None,
    validate: bool = True,
    verbose: bool = False
) -> bool:
    """
    Generate incremental data distributed across a date range.
    
    All parameters default to config file or environment variables.
    """
    try:
        # Load defaults from config (YAML + env vars)
        cfg = load_config()
        
        # Parse dates - CLI overrides config
        start = None
        end = None
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            cfg.incremental.start_date = start
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            cfg.incremental.end_date = end
        
        # Use config dates if CLI didn't provide them
        start = start or cfg.incremental.start_date or date.today()
        end = end or cfg.incremental.end_date or date.today()
        
        # Override config with CLI args if provided
        if new_customers is not None:
            cfg.incremental.new_customers = new_customers
        if new_accounts is not None:
            cfg.incremental.new_accounts = new_accounts
        if new_orders is not None:
            cfg.incremental.new_orders = new_orders
        if new_interactions is not None:
            cfg.incremental.new_interactions = new_interactions
        if new_loyalty is not None:
            cfg.incremental.new_loyalty_transactions = new_loyalty
        if output_dir is not None:
            cfg.paths.incremental_output_dir = output_dir
        if keys_cache is not None:
            cfg.paths.keys_cache = keys_cache
        if seed is not None:
            cfg.settings.seed = seed
        
        console.print(f"\n[bold blue]Generating Incremental Data: {start} to {end}[/bold blue]\n")
        
        # Show configuration
        _show_incremental_config(start, end, cfg)
        
        # Create generator
        gen = DataGenerator(config=cfg)
        
        # Load existing keys
        cache_file = cfg.paths.keys_cache
        if cache_file and Path(cache_file).exists():
            console.print(f"[dim]Loading keys from cache: {cache_file}[/dim]")
            gen.load_keys_from_cache(cache_file)
        else:
            console.print("[dim]Initializing with empty key state (first run)[/dim]")
        
        # Generate data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Generating incremental data...", total=100)
            progress.update(task, description="Generating customers and orders...")
            result = gen.generate_incremental(start_date=start, end_date=end)
            progress.update(task, completed=100)
        
        console.print()
        
        # Show results - pass all existing keys for proper validation of incremental data
        # (includes dimensions AND facts like fact_sales for sale_key references)
        existing_keys = gen.keys_loader.get_all_keys()
        _show_generation_results(result, validate, verbose, existing_keys=existing_keys)
        
        # Save to CSV - use date range in folder name
        date_folder = f"{start.strftime('%Y-%m-%d')}_to_{end.strftime('%Y-%m-%d')}"
        output_path = Path(cfg.paths.incremental_output_dir) / date_folder
        console.print(f"\n[bold]Saving to: {output_path.absolute()}[/bold]")
        file_paths = gen.save_to_csv(result, str(output_path))
        console.print(f"[green]✓ Saved {len(file_paths)} CSV files[/green]")
        
        # Save updated keys cache
        gen.save_keys_to_cache(cache_file)
        console.print(f"[dim]Updated keys cache: {cache_file}[/dim]")

        # Refresh cache from warehouse
        console.print("[dim]Refreshing keys cache from warehouse...[/dim]")
        cache_keys_command(output_file=cache_file, verbose=verbose)

        console.print()
        logger.info(f"Incremental generation complete: {result.total_records} records")
        return True
        
    except Exception as e:
        console.print(f"\n[red]✗ Error generating incremental data: {e}[/red]")
        logger.error(f"Incremental generation failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# INVENTORY SNAPSHOT MODE
# =============================================================================

def generate_inventory_command(
    target_date: Optional[str] = None,
    stores: Optional[str] = None,
    output_dir: Optional[str] = None,
    keys_cache: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """Generate inventory snapshot data (periodic)."""
    try:
        cfg = load_config()
        
        if target_date:
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            target = date.today()
        
        out_dir = output_dir or cfg.paths.incremental_output_dir
        cache_file = keys_cache or cfg.paths.keys_cache
        
        console.print(f"\n[bold blue]Generating Inventory Snapshot for: {target}[/bold blue]\n")
        
        gen = DataGenerator(config=cfg)
        
        if cache_file and Path(cache_file).exists():
            gen.load_keys_from_cache(cache_file)
        else:
            console.print("[yellow]Warning: No keys cache provided. Using defaults.[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Generating inventory snapshot...", total=None)
            data = gen.generate_inventory_snapshot(target)
        
        console.print()
        console.print(f"[green]✓ Generated {data.row_count:,} inventory records[/green]")
        
        output_path = Path(out_dir) / "inventory" / target.strftime("%Y-%m-%d")
        output_path.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_path / "fact_inventory_snapshots.csv"
        data.data.to_csv(csv_path, index=False)
        console.print(f"[dim]Saved to: {csv_path}[/dim]")
        
        if cache_file:
            gen.save_keys_to_cache(cache_file)
            console.print("[dim]Refreshing keys cache from warehouse...[/dim]")
            cache_keys_command(output_file=cache_file, verbose=verbose)

        console.print()
        return True

    except Exception as e:
        console.print(f"\n[red]✗ Error generating inventory snapshot: {e}[/red]")
        logger.error(f"Inventory snapshot generation failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# NEW STORE MODE
# =============================================================================

def generate_store_command(
    store_name: str,
    store_type: Optional[str] = None,
    region: Optional[str] = None,
    employees: Optional[int] = None,
    include_inventory: Optional[bool] = None,
    output_dir: Optional[str] = None,
    keys_cache: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """Generate data for a new store opening (event-driven)."""
    try:
        cfg = load_config()
        
        s_type = store_type or "Mall"
        s_region = region or "Northeast"
        num_employees = employees if employees is not None else cfg.incremental.employees_per_store
        gen_inventory = include_inventory if include_inventory is not None else cfg.incremental.include_initial_inventory
        out_dir = output_dir or cfg.paths.incremental_output_dir
        cache_file = keys_cache or cfg.paths.keys_cache
        
        console.print(f"\n[bold blue]Adding New Store: {store_name}[/bold blue]\n")
        
        gen = DataGenerator(config=cfg)
        
        if cache_file and Path(cache_file).exists():
            gen.load_keys_from_cache(cache_file)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Creating new store...", total=None)
            result = gen.generate_store_opening(
                store_name=store_name,
                store_type=s_type,
                region=s_region,
                employees=num_employees,
                include_inventory=gen_inventory
            )
        
        console.print()
        _show_generation_results(result, validate=False, verbose=verbose)
        
        output_path = Path(out_dir) / "stores" / store_name.lower().replace(" ", "_")
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_paths = gen.save_to_csv(result, str(output_path))
        console.print(f"[green]✓ Saved {len(file_paths)} CSV files[/green]")
        
        if cache_file:
            gen.save_keys_to_cache(cache_file)
            console.print("[dim]Refreshing keys cache from warehouse...[/dim]")
            cache_keys_command(output_file=cache_file, verbose=verbose)

        console.print()
        return True

    except Exception as e:
        console.print(f"\n[red]✗ Error adding new store: {e}[/red]")
        logger.error(f"New store generation failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# PROMOTION CAMPAIGN MODE
# =============================================================================

def generate_promotion_command(
    campaign_name: str,
    start_date: str,
    end_date: str,
    discount_min: Optional[float] = None,
    discount_max: Optional[float] = None,
    output_dir: Optional[str] = None,
    keys_cache: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """Generate data for a promotion campaign (event-driven)."""
    try:
        cfg = load_config()
        
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        d_min = discount_min if discount_min is not None else cfg.incremental.discount_min
        d_max = discount_max if discount_max is not None else cfg.incremental.discount_max
        out_dir = output_dir or cfg.paths.incremental_output_dir
        cache_file = keys_cache or cfg.paths.keys_cache
        
        console.print(f"\n[bold blue]Creating Promotion Campaign: {campaign_name}[/bold blue]\n")
        console.print(f"[dim]Period: {start} to {end}[/dim]")
        console.print(f"[dim]Discount: {d_min*100:.0f}% - {d_max*100:.0f}%[/dim]\n")
        
        gen = DataGenerator(config=cfg)
        
        if cache_file and Path(cache_file).exists():
            gen.load_keys_from_cache(cache_file)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Creating promotion campaign...", total=None)
            result = gen.generate_promotion_campaign(
                campaign_name=campaign_name,
                start_date=start,
                end_date=end,
                discount_min=d_min,
                discount_max=d_max
            )
        
        console.print()
        _show_generation_results(result, validate=False, verbose=verbose)
        
        output_path = Path(out_dir) / "promotions" / campaign_name.lower().replace(" ", "_")
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_paths = gen.save_to_csv(result, str(output_path))
        console.print(f"[green]✓ Saved {len(file_paths)} CSV files[/green]")
        
        if cache_file:
            gen.save_keys_to_cache(cache_file)
            console.print("[dim]Refreshing keys cache from warehouse...[/dim]")
            cache_keys_command(output_file=cache_file, verbose=verbose)

        console.print()
        return True

    except Exception as e:
        console.print(f"\n[red]✗ Error creating promotion: {e}[/red]")
        logger.error(f"Promotion generation failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# CACHE KEYS COMMAND
# =============================================================================

def cache_keys_command(
    output_file: Optional[str] = None,
    schema: Optional[str] = None,
    verbose: bool = False
) -> bool:
    """Cache existing surrogate keys from the configured warehouse to a local file."""
    try:
        import os
        from src.connectors import get_connector
        from src.cli.config import get_dwh_platform

        cfg = load_config()
        out_file = output_file or cfg.paths.keys_cache

        platform = get_dwh_platform()
        is_snowflake = platform in ("sf", "snowflake")

        if schema is None:
            if is_snowflake:
                schema = os.getenv("SNOWFLAKE_SCHEMA", "ECOMMERCE_DWH")
            else:
                schema = os.getenv("POSTGRES_SCHEMA", "public")

        console.print(f"\n[bold blue]Caching Keys from {platform.upper()}[/bold blue]\n")

        loader = ExistingKeysLoader()

        with get_connector(platform) as conn:
            console.print(f"[dim]Connected to {platform.upper()}[/dim]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                progress.add_task("Loading keys...", total=None)
                loader.load_from_snowflake(
                    connector=conn,
                    schema=schema,
                    load_all_keys=True
                )
        
        output_path = Path(out_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        loader.save_to_cache(str(output_path))
        
        console.print()
        console.print(f"[green]✓ Cached keys for {len(loader._key_cache)} tables[/green]")
        console.print(f"[dim]Saved to: {out_file}[/dim]")
        
        if verbose:
            summary = loader.summary()
            for table, info in summary["tables"].items():
                console.print(f"  [dim]{table}: max_key={info['max_key']}, rows={info['row_count']}[/dim]")
        
        console.print()
        return True
        
    except Exception as e:
        console.print(f"\n[red]✗ Error caching keys: {e}[/red]")
        logger.error(f"Key caching failed: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _show_initial_config(cfg: DataGenConfig) -> None:
    """Display initial load configuration table."""
    config_table = Table(title="Initial Load Configuration", show_header=True)
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", justify="right")
    
    config_table.add_row("Customers", f"{cfg.volumes.customers:,}")
    config_table.add_row("Products", f"{cfg.volumes.products:,}")
    config_table.add_row("Sales/Orders", f"{cfg.volumes.sales:,}")
    config_table.add_row("Stores", f"{cfg.volumes.stores:,}")
    config_table.add_row("Employees", f"{cfg.volumes.employees:,}")
    config_table.add_row("Promotions", f"{cfg.volumes.promotions:,}")
    config_table.add_row("Inventory Snapshots", f"{cfg.volumes.inventory_snapshots:,}")
    config_table.add_row("Customer Interactions", f"{cfg.volumes.customer_interactions:,}")
    config_table.add_row("Loyalty Transactions", f"{cfg.volumes.loyalty_transactions:,}")
    config_table.add_row("Date Range", f"{cfg.dates.start} to {cfg.dates.end}")
    if cfg.settings.seed:
        config_table.add_row("Random Seed", str(cfg.settings.seed))
    
    console.print(config_table)
    console.print()


def _show_incremental_config(start_date: date, end_date: date, cfg: DataGenConfig) -> None:
    """Display incremental operations configuration table."""
    config_table = Table(title="Incremental Operations Configuration", show_header=True)
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", justify="right")
    
    config_table.add_row("Date Range", f"{start_date} to {end_date}")
    days = (end_date - start_date).days + 1
    config_table.add_row("Days", f"{days}")
    config_table.add_row("New Customers", f"{cfg.incremental.new_customers:,}")
    config_table.add_row("New Accounts", f"{cfg.incremental.new_accounts:,}")
    config_table.add_row("New Orders", f"{cfg.incremental.new_orders:,}")
    config_table.add_row("New Interactions", f"{cfg.incremental.new_interactions:,}")
    config_table.add_row("New Loyalty Txns", f"{cfg.incremental.new_loyalty_transactions:,}")
    config_table.add_row("Existing Customer Ratio", f"{cfg.incremental.existing_customer_ratio:.0%}")
    if cfg.settings.seed:
        config_table.add_row("Random Seed", str(cfg.settings.seed))
    
    console.print(config_table)
    console.print()


def _show_generation_results(
    result,
    validate: bool,
    verbose: bool,
    existing_keys: Optional[Dict[str, List[int]]] = None
) -> None:
    """Display generation results table."""
    results_table = Table(title="Generated Data Summary", show_header=True)
    results_table.add_column("Table", style="cyan")
    results_table.add_column("Records", justify="right")
    results_table.add_column("Type", style="dim")
    
    # Dimension tables
    for name, data in sorted(result.dimensions.items()):
        results_table.add_row(name, f"{data.row_count:,}", "Dimension")
    
    # Fact tables
    for name, data in sorted(result.facts.items()):
        table_type = "Bridge" if name.startswith("bridge_") else "Fact"
        results_table.add_row(name, f"{data.row_count:,}", table_type)
    
    console.print(results_table)
    console.print(f"\n[bold]Total records: {result.total_records:,}[/bold]")
    
    # Validation
    if validate:
        handler = ReferentialIntegrityHandler()
        all_data = result.get_all_data()
        if all_data:
            is_valid = handler.validate(all_data, existing_keys=existing_keys)
            errors = handler.get_validation_errors()
            
            if is_valid:
                console.print("\n[green]✓ Referential integrity validation passed[/green]")
            else:
                console.print(f"\n[yellow]⚠ {len(errors)} referential integrity warnings[/yellow]")
                if verbose:
                    for err in errors[:5]:
                        console.print(f"  [dim]{err}[/dim]")
                    if len(errors) > 5:
                        console.print(f"  [dim]... and {len(errors) - 5} more[/dim]")
