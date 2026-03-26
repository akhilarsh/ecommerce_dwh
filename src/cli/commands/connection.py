"""
Connection command for testing DWH connectivity.

Supports multiple DWH platforms via the connector factory.
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.connectors import DEFAULT_DWH, get_connector, get_dwh_display_name
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def test_connection_command(
    dwh: str = DEFAULT_DWH,
    verbose: bool = False,
    timeout: int = 30
) -> bool:
    """
    Test DWH connection and display connection details.
    
    Args:
        dwh: DWH platform shorthand (sf, bq, rs, db)
        verbose: Enable verbose output
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    platform_name = get_dwh_display_name(dwh)
    console.print(f"\n[bold]Testing {platform_name} Connection...[/bold]\n")
    
    try:
        connector = get_connector(dwh)
        
        with connector:
            # Get connection details using unified interface
            info = connector.get_connection_info()
            
            if info.get("connected"):
                # Create status table
                table = Table(title="Connection Status", show_header=True)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Status", "✓ Connected")
                table.add_row("Platform", platform_name)
                
                # Add platform-specific fields
                display_fields = [
                    ("account", "Account"),
                    ("region", "Region"),
                    ("host", "Host"),
                    ("port", "Port"),
                    ("project", "Project"),  # BigQuery
                    ("cluster", "Cluster"),  # Redshift/Databricks
                    ("user", "User"),
                    ("role", "Role"),
                    ("warehouse", "Warehouse"),
                    ("database", "Database"),
                    ("schema", "Schema"),
                ]
                
                for field, label in display_fields:
                    if field in info and info[field]:
                        table.add_row(label, str(info[field]))
                
                console.print(table)
                console.print(f"\n[bold green]✓ {platform_name} connection test successful![/bold green]\n")
                
                logger.info(f"{platform_name} connection test passed")
                return True
            else:
                console.print("[bold red]✗ Failed to get connection details[/bold red]\n")
                return False
                
    except ValueError as e:
        console.print(f"[bold red]✗ Configuration Error:[/bold red] {e}\n")
        console.print("[dim]Check your .env file or environment variables.[/dim]")
        logger.error(f"Connection configuration error: {e}")
        return False
        
    except Exception as e:
        console.print(f"[bold red]✗ Connection Failed:[/bold red] {e}\n")
        logger.error(f"Connection test failed: {e}")
        return False


def get_connection_info(dwh: str = DEFAULT_DWH) -> Optional[dict]:
    """
    Get current connection information without verbose output.
    
    Args:
        dwh: DWH platform shorthand (sf, bq, rs, db)
    
    Returns:
        Dictionary with connection info or None if failed
    """
    try:
        connector = get_connector(dwh)
        
        with connector:
            return connector.get_connection_info()
        
    except Exception as e:
        logger.error(f"Failed to get connection info: {e}")
        return {"connected": False, "error": str(e)}
