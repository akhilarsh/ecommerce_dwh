"""
Execution workflows for the e-commerce data warehouse.

Provides high-level workflows for common operations:
- Table setup (one-time table creation)
"""

from src.workflows.base_workflow import BaseWorkflow, WorkflowResult
from src.workflows.table_setup_workflow import (
    TableSetupWorkflow,
    TableSetupConfig,
    # Backwards compatibility aliases
    SchemaCreationWorkflow,
    SchemaWorkflowConfig,
)

__all__ = [
    # Base classes
    "BaseWorkflow",
    "WorkflowResult",
    # Table setup
    "TableSetupWorkflow",
    "TableSetupConfig",
    # Backwards compatibility
    "SchemaCreationWorkflow",
    "SchemaWorkflowConfig",
]
