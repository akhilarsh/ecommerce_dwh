"""
Run arbitrary SQL files against the configured DWH platform.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.connectors import get_connector
from src.cli.config import get_dwh_platform
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_sql_command(
    sql_file: str,
    verbose: bool = False
) -> bool:
    """
    Execute a SQL file against Snowflake.
    
    Splits on semicolons and executes each statement.
    Skips empty statements and comments-only blocks.
    
    Args:
        sql_file: Path to the .sql file
        verbose: Show each statement before executing
        
    Returns:
        True if all statements succeeded
    """
    path = Path(sql_file)
    if not path.exists():
        console.print(f"[red]✗ File not found: {sql_file}[/red]")
        return False
    
    sql_text = path.read_text().strip()
    if not sql_text:
        console.print(f"[yellow]⚠ Empty SQL file: {sql_file}[/yellow]")
        return True
    
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    # Filter out comment-only blocks
    statements = [
        s for s in statements
        if any(line.strip() and not line.strip().startswith("--") for line in s.splitlines())
    ]
    
    if not statements:
        console.print(f"[yellow]⚠ No executable statements in {sql_file}[/yellow]")
        return True
    
    console.print(f"[bold]Running {path.name}[/bold] ({len(statements)} statement{'s' if len(statements) != 1 else ''})\n")
    
    try:
        platform = get_dwh_platform()
        with get_connector(platform) as connector:
            for i, stmt in enumerate(statements, 1):
                if verbose:
                    console.print(Panel(stmt, title=f"Statement {i}/{len(statements)}", border_style="dim"))

                result = connector.execute_query(stmt)

                rows_affected = len(result) if result else 0
                console.print(f"  [green]✓[/green] Statement {i}: {rows_affected} row{'s' if rows_affected != 1 else ''} returned/affected")

            # Commit after all statements succeed (required for Postgres DDL)
            if hasattr(connector, "commit"):
                connector.commit()

            console.print(f"\n[green]✓ All {len(statements)} statement(s) executed successfully[/green]")
            return True
            
    except Exception as e:
        console.print(f"\n[red]✗ SQL execution failed: {e}[/red]")
        logger.error(f"SQL execution failed: {e}")
        return False
