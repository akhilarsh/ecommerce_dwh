"""
Config commands for managing DWH CLI settings.

Commands:
    dwh config set-wh <platform>  # Set DWH platform
    dwh config show               # Show current configuration
    dwh config clear              # Clear DWH platform setting
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.config import get_config, ENV_VAR_PLATFORM
from src.connectors import get_dwh_display_name, list_supported_dwh
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


@click.group("config")
def config_group():
    """Manage DWH CLI configuration."""
    pass


@config_group.command("set-wh")
@click.argument("platform")
@click.option(
    "--local", "-l",
    is_flag=True,
    help="Save to local project config (.dwh.yaml) instead of global (~/.dwh/config.yaml)"
)
def set_wh(platform: str, local: bool):
    """
    Set the DWH platform.
    
    PLATFORM is the shorthand or full name (sf, snowflake, bq, bigquery, etc.)
    
    Examples:
    
        dwh config set-wh sf          # Set Snowflake globally
        
        dwh config set-wh bq --local  # Set BigQuery for this project only
    """
    try:
        config = get_config()
        config_path = config.set_platform(platform, local=local)
        
        display_name = get_dwh_display_name(platform)
        scope = "local project" if local else "global"
        
        console.print(f"\n[bold green]✓[/bold green] Set DWH platform to [cyan]{display_name}[/cyan] ({scope})")
        console.print(f"[dim]Config saved to: {config_path}[/dim]\n")
        
    except ValueError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}\n")
        raise SystemExit(1)


@config_group.command("show")
def show():
    """
    Show current DWH configuration.
    
    Displays the active platform and all configuration sources.
    """
    config = get_config()
    info = config.get_config_info()
    
    # Active configuration panel
    if info["active_platform"]:
        display_name = get_dwh_display_name(info["active_platform"])
        console.print(Panel(
            f"[bold cyan]{display_name}[/bold cyan] ({info['active_platform']})\n"
            f"[dim]Source: {info['active_source']}[/dim]",
            title="Active DWH Platform",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[yellow]No DWH platform configured[/yellow]\n"
            f"[dim]Run 'dwh config set-wh <platform>' to set one[/dim]",
            title="Active DWH Platform",
            border_style="yellow"
        ))
    
    # Configuration sources table
    table = Table(title="Configuration Sources", show_header=True)
    table.add_column("Source", style="cyan")
    table.add_column("Platform", style="green")
    table.add_column("Location", style="dim")
    
    # Environment variable
    env_val = info["env_var"] or "-"
    table.add_row(
        f"Environment ({ENV_VAR_PLATFORM})",
        env_val,
        "Environment variable"
    )
    
    # Local config
    local_platform = info["local_config"].get("platform", "-")
    local_exists = "✓" if info["local_config_path"].exists() else "✗"
    table.add_row(
        f"Local Config {local_exists}",
        local_platform,
        str(info["local_config_path"])
    )
    
    # Global config
    global_platform = info["global_config"].get("platform", "-")
    global_exists = "✓" if info["global_config_path"].exists() else "✗"
    table.add_row(
        f"Global Config {global_exists}",
        global_platform,
        str(info["global_config_path"])
    )
    
    console.print()
    console.print(table)
    
    # Supported platforms
    console.print(f"\n[dim]Supported platforms: {', '.join(list_supported_dwh())}[/dim]\n")


@config_group.command("clear")
@click.option(
    "--local", "-l",
    is_flag=True,
    help="Clear from local project config instead of global"
)
@click.option(
    "--all", "-a", "clear_all",
    is_flag=True,
    help="Clear from both local and global config"
)
def clear(local: bool, clear_all: bool):
    """
    Clear the DWH platform setting.
    
    Examples:
    
        dwh config clear           # Clear global config
        
        dwh config clear --local   # Clear local project config
        
        dwh config clear --all     # Clear both
    """
    config = get_config()
    cleared = []
    
    if clear_all or local:
        path = config.clear_platform(local=True)
        if path:
            cleared.append(f"local ({path})")
    
    if clear_all or not local:
        path = config.clear_platform(local=False)
        if path:
            cleared.append(f"global ({path})")
    
    if cleared:
        console.print(f"\n[bold green]✓[/bold green] Cleared DWH platform from: {', '.join(cleared)}\n")
    else:
        console.print("\n[yellow]No platform setting found to clear[/yellow]\n")
