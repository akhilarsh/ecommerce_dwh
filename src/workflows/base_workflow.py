"""
Base workflow classes and result types.

Provides common types and patterns used by all execution workflows.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    
    success: bool
    workflow_name: str
    started_at: datetime
    completed_at: datetime
    stages_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Duration of workflow execution in seconds."""
        return (self.completed_at - self.started_at).total_seconds()
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"<WorkflowResult: {self.workflow_name} - {status} "
            f"({len(self.stages_completed)} stages, {self.duration_seconds:.2f}s)>"
        )


class BaseWorkflow(ABC):
    """
    Abstract base class for all workflows.
    
    Provides common structure and logging for workflow execution.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Workflow name identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable workflow description."""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> WorkflowResult:
        """
        Execute the workflow.
        
        Returns:
            WorkflowResult with execution details
        """
        pass
    
    def _create_result(
        self,
        success: bool,
        started_at: datetime,
        stages_completed: List[str],
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> WorkflowResult:
        """
        Create a workflow result.
        
        Args:
            success: Whether workflow succeeded
            started_at: When workflow started
            stages_completed: List of completed stage names
            error: Error message if failed
            details: Additional details dictionary
            
        Returns:
            WorkflowResult instance
        """
        return WorkflowResult(
            success=success,
            workflow_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            stages_completed=stages_completed,
            error=error,
            details=details or {}
        )
    
    def _log_start(self) -> None:
        """Log workflow start."""
        logger.info("=" * 80)
        logger.info(f"STARTING WORKFLOW: {self.name}")
        logger.info(f"Description: {self.description}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
    
    def _log_end(self, result: WorkflowResult) -> None:
        """Log workflow completion."""
        logger.info("=" * 80)
        if result.success:
            logger.info(f"✓ WORKFLOW COMPLETED SUCCESSFULLY: {self.name}")
        else:
            logger.error(f"✗ WORKFLOW FAILED: {self.name}")
            if result.error:
                logger.error(f"Error: {result.error}")
        logger.info(f"Duration: {result.duration_seconds:.2f}s")
        logger.info(f"Stages completed: {len(result.stages_completed)}")
        logger.info("=" * 80)
