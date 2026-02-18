"""
Main CLI entry point for E-Commerce Data Warehouse.

Usage:
    dwh config set-wh snowflake  # Set DWH platform (one-time setup)
    dwh config show              # Show current configuration
    dwh test-connection          # Test connection
    dwh create                   # Create tables in configured db/schema
    dwh create -t dim_dates      # Create a specific table
    dwh validate                 # Validate tables exist
    dwh setup-tables             # One-time table creation workflow
    dwh create-and-load          # Full deployment with data

Supported DWH platforms (shorthand / full name):
    sf / snowflake  - Snowflake Data Cloud
    bq / bigquery   - Google BigQuery (placeholder)
    rs / redshift   - Amazon Redshift (placeholder)
    db / databricks - Databricks (placeholder)

Configuration priority:
    1. Environment variable (DWH_PLATFORM)
    2. Local project config (.dwh.yaml)
    3. Global config (~/.dwh/config.yaml)
"""

import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables
load_dotenv()

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.cli.config import get_config, get_dwh_platform
from src.connectors import get_dwh_display_name, list_supported_dwh
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def print_banner():
    """Print CLI banner."""
    # Try to show configured platform in banner
    try:
        config = get_config()
        info = config.get_config_info()
        if info["active_platform"]:
            platform_name = get_dwh_display_name(info["active_platform"])
        else:
            platform_name = "Multi-Platform"
    except Exception:
        platform_name = "Multi-Platform"
    
    console.print(Panel.fit(
        "[bold blue]E-Commerce Data Warehouse CLI[/bold blue]\n"
        f"[dim]{platform_name} Data Warehouse Management Tool[/dim]",
        border_style="blue"
    ))


def require_dwh_platform(ctx: click.Context) -> str:
    """
    Get the configured DWH platform or raise a helpful error.
    
    Args:
        ctx: Click context
        
    Returns:
        DWH platform shorthand
        
    Raises:
        click.UsageError: If no platform is configured
    """
    try:
        return get_dwh_platform()
    except ValueError as e:
        raise click.UsageError(str(e))


@click.group()
@click.version_option(version="1.0.0", prog_name="dwh")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool):
    """
    E-Commerce Data Warehouse CLI.
    
    A command-line tool for managing the E-Commerce Data Warehouse.
    
    First, configure your DWH platform:
    
        dwh config set-wh sf    # Set to Snowflake
        
        dwh config show         # View current config
    
    Then run commands:
    
        dwh test-connection     # Test connection
        
        dwh create              # Create tables
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    
    if verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command("test-connection")
@click.option("--timeout", default=30, help="Connection timeout in seconds")
@click.pass_context
def test_connection(ctx: click.Context, timeout: int):
    """Test connection to the configured DWH platform."""
    from src.cli.commands.connection import test_connection_command
    dwh = require_dwh_platform(ctx)
    test_connection_command(
        dwh=dwh,
        verbose=ctx.obj.get("verbose", False),
        timeout=timeout
    )


@cli.command("generate-sql")
@click.option("--output-dir", "-o", default="outputs/generated_sql", help="Output directory for SQL files")
@click.option("--include-drops", is_flag=True, help="Include DROP TABLE statements")
@click.option("--table", "-t", default=None, help="Generate SQL for a specific table only (e.g., dim_customers)")
@click.pass_context
def generate_sql(ctx: click.Context, output_dir: str, include_drops: bool, table: Optional[str]):
    """Generate E-Commerce Data Warehouse DDL/DML SQL files."""
    from src.cli.commands.generate_sql import generate_sql_command
    generate_sql_command(
        output_dir=output_dir,
        include_drops=include_drops,
        table_name=table,
        verbose=ctx.obj.get("verbose", False)
    )


@cli.command("create")
@click.option("--skip-fk", is_flag=True, help="Skip foreign key constraints")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--table", "-t", default=None, help="Create a specific table only (e.g., dim_customers)")
@click.pass_context
def create(ctx: click.Context, skip_fk: bool, dry_run: bool, table: Optional[str]):
    """Create tables in the configured database/schema."""
    from src.cli.commands.create_tables import create_tables_command
    dwh = require_dwh_platform(ctx)
    create_tables_command(
        skip_fk=skip_fk,
        dry_run=dry_run,
        table_name=table,
        verbose=ctx.obj.get("verbose", False)
    )


@cli.command("validate")
@click.option("--check-fk", is_flag=True, help="Validate foreign key constraints")
@click.option("--check-data", is_flag=True, help="Check for data presence")
@click.pass_context
def validate(ctx: click.Context, check_fk: bool, check_data: bool):
    """Validate E-Commerce Data Warehouse table creation."""
    from src.cli.commands.validate import validate_command
    validate_command(
        check_fk=check_fk,
        check_data=check_data,
        verbose=ctx.obj.get("verbose", False)
    )


@cli.command("generate-initial")
@click.option("--customers", default=None, type=int, help="Number of customers (default from DATAGEN_CUSTOMERS env)")
@click.option("--products", default=None, type=int, help="Number of products (default from DATAGEN_PRODUCTS env)")
@click.option("--orders", default=None, type=int, help="Number of orders (default from DATAGEN_SALES env)")
@click.option("--stores", default=None, type=int, help="Number of stores (default from DATAGEN_STORES env)")
@click.option("--employees", default=None, type=int, help="Number of employees (default from DATAGEN_EMPLOYEES env)")
@click.option("--output-dir", "-o", default=None, help="Output directory (default from DATAGEN_OUTPUT_DIR env)")
@click.option("--seed", default=None, type=int, help="Random seed (default from DATAGEN_SEED env)")
@click.option("--no-validate", is_flag=True, help="Skip referential integrity validation")
@click.pass_context
def generate_initial(
    ctx: click.Context,
    customers: Optional[int],
    products: Optional[int],
    orders: Optional[int],
    stores: Optional[int],
    employees: Optional[int],
    output_dir: Optional[str],
    seed: Optional[int],
    no_validate: bool
):
    """Generate initial/bulk load data for all tables (first-time setup)."""
    from src.cli.commands.generate_data import generate_initial_command
    success = generate_initial_command(
        customers=customers,
        products=products,
        orders=orders,
        stores=stores,
        employees=employees,
        output_dir=output_dir,
        seed=seed,
        validate=not no_validate,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("generate-incremental")
@click.option("--start-date", "-s", default=None, help="Start date (YYYY-MM-DD), defaults to config")
@click.option("--end-date", "-e", default=None, help="End date (YYYY-MM-DD), defaults to config")
@click.option("--customers", default=None, type=int, help="New customers (default from config)")
@click.option("--orders", default=None, type=int, help="New orders (default from config)")
@click.option("--interactions", default=None, type=int, help="New interactions (default from config)")
@click.option("--loyalty", default=None, type=int, help="New loyalty txns (default from config)")
@click.option("--output-dir", "-o", default=None, help="Output directory (default from config)")
@click.option("--keys-cache", "-k", default=None, help="Keys cache file (default from config)")
@click.option("--seed", default=None, type=int, help="Random seed (default from config)")
@click.option("--no-validate", is_flag=True, help="Skip referential integrity validation")
@click.pass_context
def generate_incremental(
    ctx: click.Context,
    start_date: Optional[str],
    end_date: Optional[str],
    customers: Optional[int],
    orders: Optional[int],
    interactions: Optional[int],
    loyalty: Optional[int],
    output_dir: Optional[str],
    keys_cache: Optional[str],
    seed: Optional[int],
    no_validate: bool
):
    """Generate incremental data distributed across a date range. Defaults from config."""
    from src.cli.commands.generate_data import generate_incremental_command
    success = generate_incremental_command(
        start_date=start_date,
        end_date=end_date,
        new_customers=customers,
        new_orders=orders,
        new_interactions=interactions,
        new_loyalty=loyalty,
        output_dir=output_dir,
        keys_cache=keys_cache,
        seed=seed,
        validate=not no_validate,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("generate-inventory")
@click.option("--date", "-d", "target_date", default=None, help="Snapshot date (YYYY-MM-DD), defaults to today")
@click.option("--stores", "-s", default=None, help="Comma-separated store keys (all if not specified)")
@click.option("--output-dir", "-o", default=None, help="Output directory (default from DATAGEN_INCREMENTAL_OUTPUT_DIR env)")
@click.option("--keys-cache", "-k", default=None, help="Keys cache file (default from DATAGEN_KEYS_CACHE env)")
@click.pass_context
def generate_inventory(
    ctx: click.Context,
    target_date: Optional[str],
    stores: Optional[str],
    output_dir: Optional[str],
    keys_cache: Optional[str]
):
    """Generate inventory snapshot data (periodic). Defaults from DATAGEN_* env vars."""
    from src.cli.commands.generate_data import generate_inventory_command
    success = generate_inventory_command(
        target_date=target_date,
        stores=stores,
        output_dir=output_dir,
        keys_cache=keys_cache,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("generate-store")
@click.argument("store_name")
@click.option("--type", "-t", "store_type", default=None, help="Store type (Flagship, Mall, Outlet, etc.)")
@click.option("--region", "-r", default=None, help="Store region")
@click.option("--employees", "-e", default=None, type=int, help="Employees to hire (default from DATAGEN_EMPLOYEES_PER_NEW_STORE env)")
@click.option("--no-inventory", is_flag=True, help="Skip initial inventory generation")
@click.option("--output-dir", "-o", default=None, help="Output directory (default from DATAGEN_INCREMENTAL_OUTPUT_DIR env)")
@click.option("--keys-cache", "-k", default=None, help="Keys cache file (default from DATAGEN_KEYS_CACHE env)")
@click.pass_context
def generate_store(
    ctx: click.Context,
    store_name: str,
    store_type: Optional[str],
    region: Optional[str],
    employees: Optional[int],
    no_inventory: bool,
    output_dir: Optional[str],
    keys_cache: Optional[str]
):
    """Generate data for a new store opening (event-driven). Defaults from DATAGEN_* env vars."""
    from src.cli.commands.generate_data import generate_store_command
    success = generate_store_command(
        store_name=store_name,
        store_type=store_type,
        region=region,
        employees=employees,
        include_inventory=None if no_inventory else True,
        output_dir=output_dir,
        keys_cache=keys_cache,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("generate-promotion")
@click.argument("campaign_name")
@click.option("--start", "-s", "start_date", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", "end_date", required=True, help="End date (YYYY-MM-DD)")
@click.option("--discount-min", default=None, type=float, help="Min discount (default from DATAGEN_PROMO_DISCOUNT_MIN env)")
@click.option("--discount-max", default=None, type=float, help="Max discount (default from DATAGEN_PROMO_DISCOUNT_MAX env)")
@click.option("--output-dir", "-o", default=None, help="Output directory (default from DATAGEN_INCREMENTAL_OUTPUT_DIR env)")
@click.option("--keys-cache", "-k", default=None, help="Keys cache file (default from DATAGEN_KEYS_CACHE env)")
@click.pass_context
def generate_promotion(
    ctx: click.Context,
    campaign_name: str,
    start_date: str,
    end_date: str,
    discount_min: Optional[float],
    discount_max: Optional[float],
    output_dir: Optional[str],
    keys_cache: Optional[str]
):
    """Generate data for a promotion campaign (event-driven). Defaults from DATAGEN_* env vars."""
    from src.cli.commands.generate_data import generate_promotion_command
    success = generate_promotion_command(
        campaign_name=campaign_name,
        start_date=start_date,
        end_date=end_date,
        discount_min=discount_min,
        discount_max=discount_max,
        output_dir=output_dir,
        keys_cache=keys_cache,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("cache-keys")
@click.option("--output", "-o", default=None, help="Output path (default from DATAGEN_KEYS_CACHE env)")
@click.option("--schema", "-s", default="ECOMMERCE_DWH", help="Schema name in Snowflake")
@click.pass_context
def cache_keys(
    ctx: click.Context,
    output: Optional[str],
    schema: str
):
    """Cache existing surrogate keys from Snowflake for incremental generation."""
    dwh = require_dwh_platform(ctx)
    from src.cli.commands.generate_data import cache_keys_command
    success = cache_keys_command(
        output_file=output,
        schema=schema,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("load-data")
@click.option("--mode", "-m", type=click.Choice(["initial", "incremental"]), default="incremental",
              help="Load mode: 'initial' (from output_dir) or 'incremental' (from incremental_output_dir)")
@click.option("--input-dir", "-i", default=None, help="Override input directory for CSV files")
@click.option("--batch-size", default=10000, help="Batch size for loading")
@click.option("--truncate", is_flag=True, help="Truncate tables before loading")
@click.option("--table", "-t", default=None, help="Load data for a specific table only")
@click.option("--no-validate", is_flag=True, help="Skip row count validation after loading")
@click.option("--resume", "-r", is_flag=True, help="Resume from last state, skipping already loaded tables")
@click.option("--show-state", is_flag=True, help="Show current load state without loading")
@click.option("--clear-state", is_flag=True, help="Clear saved load state")
@click.pass_context
def load_data(
    ctx: click.Context,
    mode: str,
    input_dir: Optional[str],
    batch_size: int,
    truncate: bool,
    table: Optional[str],
    no_validate: bool,
    resume: bool,
    show_state: bool,
    clear_state: bool
):
    """
    Load data into the configured DWH platform.
    
    Uses mode to determine input folder from datagen_config.yaml:
    
    \b
      --mode initial      Uses paths.output_dir (default: outputs/initial_data)
      --mode incremental  Uses paths.incremental_output_dir (default: outputs/incremental_data)
    
    Use -i/--input-dir to override the default folder for either mode.
    
    Resume capability for partial failures:
    
    \b
      --resume       Continue from last state, skipping successful tables
      --show-state   Display current load state
      --clear-state  Reset load state for fresh start
    """
    from src.cli.commands.load_data import (
        load_data_command,
        show_load_state,
        clear_load_state,
    )
    
    # Handle state inspection commands
    if show_state:
        show_load_state()
        return
    
    if clear_state:
        clear_load_state()
        return
    
    dwh = require_dwh_platform(ctx)
    success = load_data_command(
        input_dir=input_dir,
        mode=mode,
        batch_size=batch_size,
        truncate=truncate,
        table_name=table,
        platform=dwh,
        validate=not no_validate,
        resume=resume,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("run-sql")
@click.argument("sql_file", type=click.Path(exists=True))
@click.pass_context
def run_sql(ctx: click.Context, sql_file: str):
    """
    Run a SQL file against the configured DWH platform.
    
    \b
    Example:
      dwh run-sql sql/05_update_lifetime_value.sql
    """
    from src.cli.commands.run_sql import run_sql_command
    dwh = require_dwh_platform(ctx)
    success = run_sql_command(
        sql_file=sql_file,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("status")
@click.pass_context
def status(ctx: click.Context):
    """Show table creation status."""
    from src.cli.commands.validate import status_command
    status_command(verbose=ctx.obj.get("verbose", False))




@cli.command("setup-tables")
@click.option("--database", "-d", default=None, help="Target database (uses env var if not provided)")
@click.option("--schema", "-s", default=None, help="Target schema (uses env var if not provided)")
@click.option("--drop-existing", is_flag=True, help="Drop and recreate existing tables (required if tables exist)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--skip-fk", is_flag=True, help="Skip FK constraints (required if tables exist and not dropping)")
@click.pass_context
def setup_tables(
    ctx: click.Context,
    database: Optional[str],
    schema: Optional[str],
    drop_existing: bool,
    dry_run: bool,
    skip_fk: bool
):
    """
    Create all tables in the data warehouse (one-time setup workflow).
    
    If tables already exist, you must specify either --drop-existing or --skip-fk.
    """
    from src.cli.commands.workflows import setup_tables_command
    dwh = require_dwh_platform(ctx)
    success = setup_tables_command(
        database=database,
        schema=schema,
        drop_existing=drop_existing,
        dry_run=dry_run,
        skip_fk=skip_fk,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("create-and-load")
@click.option("--drop-existing", is_flag=True, help="Drop and recreate existing tables (fresh deployment)")
@click.option("--skip-fk", is_flag=True, help="Skip foreign key constraints")
@click.option("--skip-load", is_flag=True, help="Only create tables, skip data generation and loading")
@click.option("--customers", default=None, type=int, help="Override number of customers (from config if not provided)")
@click.option("--products", default=None, type=int, help="Override number of products (from config if not provided)")
@click.option("--orders", default=None, type=int, help="Override number of orders (from config if not provided)")
@click.option("--stores", default=None, type=int, help="Override number of stores (from config if not provided)")
@click.option("--employees", default=None, type=int, help="Override number of employees (from config if not provided)")
@click.option("--seed", default=None, type=int, help="Override random seed (from config if not provided)")
@click.pass_context
def create_and_load(
    ctx: click.Context,
    drop_existing: bool,
    skip_fk: bool,
    skip_load: bool,
    customers: Optional[int],
    products: Optional[int],
    orders: Optional[int],
    stores: Optional[int],
    employees: Optional[int],
    seed: Optional[int]
):
    """
    Deploy tables and load data.
    
    \b
    With --drop-existing (fresh deployment):
      1. Drop all existing tables
      2. Create all tables
      3. Generate + load all data
    
    \b
    Without --drop-existing (incremental):
      1. Skip existing tables, create only new tables
      2. If new tables: generate data, load only new tables
      3. If no new tables: exit (nothing to do)
    
    For adding data to existing tables, use generate-and-load.
    """
    from src.cli.commands.workflows import create_and_load_command
    dwh = require_dwh_platform(ctx)
    success = create_and_load_command(
        drop_existing=drop_existing,
        skip_fk=skip_fk,
        skip_load=skip_load,
        customers=customers,
        products=products,
        orders=orders,
        stores=stores,
        employees=employees,
        seed=seed,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


@cli.command("generate-and-load")
@click.option("--start-date", "-s", default=None, help="Start date (YYYY-MM-DD), defaults to config")
@click.option("--end-date", "-e", default=None, help="End date (YYYY-MM-DD), defaults to config")
@click.option("--customers", default=None, type=int, help="New customers (default from config)")
@click.option("--orders", default=None, type=int, help="New orders (default from config)")
@click.option("--interactions", default=None, type=int, help="New interactions (default from config)")
@click.option("--loyalty", default=None, type=int, help="New loyalty txns (default from config)")
@click.option("--seed", default=None, type=int, help="Random seed (default from config)")
@click.option("--truncate", is_flag=True, help="Truncate tables before loading")
@click.option("--no-validate", is_flag=True, help="Skip referential integrity validation")
@click.pass_context
def generate_and_load(
    ctx: click.Context,
    start_date: Optional[str],
    end_date: Optional[str],
    customers: Optional[int],
    orders: Optional[int],
    interactions: Optional[int],
    loyalty: Optional[int],
    seed: Optional[int],
    truncate: bool,
    no_validate: bool
):
    """
    Generate incremental data and load into warehouse.
    
    Combines generate-incremental + load-data into a single workflow.
    Uses dates from datagen_config.yaml or CLI overrides.
    
    \b
    Example:
      dwh generate-and-load                          # Use config dates
      dwh generate-and-load -s 2026-02-01 -e 2026-02-06  # Override dates
    """
    from src.cli.commands.workflows import generate_and_load_command
    dwh = require_dwh_platform(ctx)
    success = generate_and_load_command(
        start_date=start_date,
        end_date=end_date,
        new_customers=customers,
        new_orders=orders,
        new_interactions=interactions,
        new_loyalty=loyalty,
        seed=seed,
        truncate=truncate,
        validate=not no_validate,
        verbose=ctx.obj.get("verbose", False)
    )
    sys.exit(0 if success else 1)


# Register config subcommand group
from src.cli.commands.config_cmd import config_group
cli.add_command(config_group)


def main():
    """Main entry point."""
    print_banner()
    cli()


if __name__ == "__main__":
    main()
