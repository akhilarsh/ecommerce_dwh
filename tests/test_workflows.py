"""
Tests for execution workflows.

Tests workflow configuration, dry-run modes, and result handling.
Integration tests that connect to Snowflake are skipped by default.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import os

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.workflows import (
    BaseWorkflow,
    TableSetupWorkflow,
    TableSetupConfig,
    # Backwards compatibility
    SchemaCreationWorkflow,
    SchemaWorkflowConfig,
    WorkflowResult,
)


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""
    
    def test_workflow_result_creation(self):
        """WorkflowResult can be created with required fields."""
        started = datetime.now()
        result = WorkflowResult(
            success=True,
            workflow_name="test_workflow",
            started_at=started,
            completed_at=datetime.now(),
            stages_completed=["stage1", "stage2"]
        )
        
        assert result.success is True
        assert result.workflow_name == "test_workflow"
        assert len(result.stages_completed) == 2
        assert result.error is None
    
    def test_workflow_result_with_error(self):
        """WorkflowResult captures error information."""
        result = WorkflowResult(
            success=False,
            workflow_name="failed_workflow",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            stages_completed=["stage1"],
            error="Connection failed"
        )
        
        assert result.success is False
        assert result.error == "Connection failed"
    
    def test_workflow_result_duration(self):
        """WorkflowResult calculates duration correctly."""
        from datetime import timedelta
        
        started = datetime.now()
        completed = started + timedelta(seconds=5)
        
        result = WorkflowResult(
            success=True,
            workflow_name="timed_workflow",
            started_at=started,
            completed_at=completed,
            stages_completed=[]
        )
        
        assert result.duration_seconds == pytest.approx(5.0, rel=0.1)
    
    def test_workflow_result_with_details(self):
        """WorkflowResult stores additional details."""
        result = WorkflowResult(
            success=True,
            workflow_name="detailed_workflow",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            stages_completed=["stage1"],
            details={"tables_created": 18, "rows_loaded": 50000}
        )
        
        assert result.details["tables_created"] == 18
        assert result.details["rows_loaded"] == 50000


class TestTableSetupConfig:
    """Tests for TableSetupConfig."""
    
    def test_default_config(self):
        """TableSetupConfig has sensible defaults."""
        config = TableSetupConfig()
        
        assert config.database is None
        assert config.schema is None
        assert config.drop_existing is False
        assert config.dry_run is False
        assert config.apply_foreign_keys is True
    
    def test_custom_config(self):
        """TableSetupConfig accepts custom values."""
        config = TableSetupConfig(
            database="TEST_DB",
            schema="TEST_SCHEMA",
            drop_existing=True,
            dry_run=True,
            apply_foreign_keys=False
        )
        
        assert config.database == "TEST_DB"
        assert config.schema == "TEST_SCHEMA"
        assert config.drop_existing is True
        assert config.dry_run is True
        assert config.apply_foreign_keys is False
    
    def test_backwards_compatibility_alias(self):
        """SchemaWorkflowConfig alias works for backwards compatibility."""
        config = SchemaWorkflowConfig(database="TEST_DB")
        assert config.database == "TEST_DB"


class TestTableSetupWorkflow:
    """Tests for TableSetupWorkflow."""
    
    def test_workflow_name_and_description(self):
        """Workflow has name and description."""
        workflow = TableSetupWorkflow()
        
        assert workflow.name == "table_setup"
        assert "table" in workflow.description.lower()
    
    def test_dry_run_mode(self):
        """Dry run mode shows what would be done without executing."""
        config = TableSetupConfig(dry_run=True)
        workflow = TableSetupWorkflow()
        
        result = workflow.run(config)
        
        assert result.success is True
        assert "dry_run" in result.stages_completed
        assert result.details.get("dry_run") is True
        assert "tables_to_create" in result.details
    
    @patch("src.workflows.table_setup_workflow.get_connector")
    @patch("src.workflows.table_setup_workflow.get_dwh_platform", return_value="sf")
    def test_connection_failure_handling(self, mock_platform, mock_get_connector):
        """Workflow handles connection failures gracefully."""
        mock_get_connector.side_effect = Exception("Connection refused")

        config = TableSetupConfig()
        workflow = TableSetupWorkflow()

        result = workflow.run(config)

        assert result.success is False
        assert result.error is not None
    
    def test_backwards_compatibility_alias(self):
        """SchemaCreationWorkflow alias works for backwards compatibility."""
        workflow = SchemaCreationWorkflow()
        assert workflow.name == "table_setup"


class TestWorkflowCLICommands:
    """Tests for CLI command functions."""
    
    @pytest.mark.skipif(
        True,
        reason="CLI tests require 'rich' module - skipped in unit tests"
    )
    def test_setup_tables_command_dry_run(self):
        """setup-tables command works in dry run mode."""
        # This test is skipped as it requires CLI dependencies
        pass
    
    @pytest.mark.skipif(
        True,
        reason="CLI tests require 'rich' module - skipped in unit tests"
    )
    def test_create_and_load_command_fresh(self):
        """create-and-load --drop-existing orchestrates fresh deployment."""
        # This test is skipped as it requires CLI dependencies
        pass
    
    @pytest.mark.skipif(
        True,
        reason="CLI tests require 'rich' module - skipped in unit tests"
    )
    def test_create_and_load_command_incremental(self):
        """create-and-load (no --drop-existing) handles incremental deployment."""
        # This test is skipped as it requires CLI dependencies
        pass


class TestTableCreatorNewTablesTracking:
    """Tests for tracking newly created tables."""
    
    @patch.dict("os.environ", {"SNOWFLAKE_DATABASE": "TEST_DB", "SNOWFLAKE_SCHEMA": "TEST_SCHEMA"})
    def test_stats_has_new_tables_list(self):
        """TableCreator stats includes new_tables_created list."""
        from src.table_manager.create_tables import TableCreator

        mock_connector = MagicMock()
        mock_connector.PLATFORM = "snowflake"
        creator = TableCreator(mock_connector)

        assert "new_tables_created" in creator.stats
        assert isinstance(creator.stats["new_tables_created"], list)
        assert len(creator.stats["new_tables_created"]) == 0
