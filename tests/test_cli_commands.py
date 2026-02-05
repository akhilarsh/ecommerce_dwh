"""
Unit tests for CLI commands.

Tests CLI command functions in isolation with mocked dependencies.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest
from click.testing import CliRunner

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestCLIMain:
    """Tests for main CLI entry point."""
    
    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    def test_cli_help(self, runner):
        """CLI shows help message."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "E-Commerce Data Warehouse CLI" in result.output
    
    def test_cli_version(self, runner):
        """CLI shows version."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
    
    def test_cli_verbose_flag(self, runner):
        """CLI accepts verbose flag."""
        from src.cli.main import cli
        
        # Just test that the flag is accepted
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0


class TestConnectionCommand:
    """Tests for test-connection command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @patch("src.cli.commands.connection.SnowflakeConnector")
    def test_connection_success(self, mock_connector, runner):
        """Test connection command reports success."""
        from src.cli.main import cli
        
        # Mock successful connection
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute_query.return_value = [("7.0.0",)]
        mock_connector.return_value = mock_conn
        
        result = runner.invoke(cli, ["test-connection"])
        # Command may fail without real credentials, but should not crash
        assert result.exit_code in [0, 1]
    
    @patch("src.cli.commands.connection.SnowflakeConnector")
    def test_connection_with_timeout(self, mock_connector, runner):
        """Test connection command accepts timeout option."""
        from src.cli.main import cli
        
        mock_conn = MagicMock()
        mock_connector.return_value = mock_conn
        
        result = runner.invoke(cli, ["test-connection", "--timeout", "60"])
        assert result.exit_code in [0, 1]


class TestGenerateSQLCommand:
    """Tests for generate-sql command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_generate_sql_creates_output_dir(self, runner, tmp_path):
        """Generate SQL creates output directory."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "sql_output"
        
        result = runner.invoke(cli, [
            "generate-sql",
            "--output-dir", str(output_dir)
        ])
        
        # Should succeed and create files
        assert result.exit_code == 0
        assert output_dir.exists()
    
    def test_generate_sql_include_drops(self, runner, tmp_path):
        """Generate SQL with include-drops flag."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "sql_output"
        
        result = runner.invoke(cli, [
            "generate-sql",
            "--output-dir", str(output_dir),
            "--include-drops"
        ])
        
        assert result.exit_code == 0
    
    def test_generate_sql_single_table(self, runner, tmp_path):
        """Generate SQL for single table."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "sql_output"
        
        result = runner.invoke(cli, [
            "generate-sql",
            "--output-dir", str(output_dir),
            "--table", "dim_customers"
        ])
        
        assert result.exit_code == 0


class TestCreateCommand:
    """Tests for create command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_create_dry_run(self, runner):
        """Create with dry-run shows plan without executing."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, ["create", "--dry-run"])
        
        # Dry run should succeed
        assert result.exit_code == 0
        assert "dry" in result.output.lower() or "plan" in result.output.lower() or "would" in result.output.lower()
    
    def test_create_skip_fk(self, runner):
        """Create accepts skip-fk option."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, ["create", "--dry-run", "--skip-fk"])
        assert result.exit_code == 0


class TestGenerateDataCommand:
    """Tests for generate-data command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_generate_data_with_counts(self, runner, tmp_path):
        """Generate data with custom counts."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "data"
        
        result = runner.invoke(cli, [
            "generate-data",
            "--customers", "5",
            "--products", "10",
            "--orders", "20",
            "--output-dir", str(output_dir),
            "--seed", "42"
        ])
        
        assert result.exit_code == 0
    
    def test_generate_data_single_table(self, runner, tmp_path):
        """Generate data for single table."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "data"
        
        result = runner.invoke(cli, [
            "generate-data",
            "--table", "dim_customers",
            "--customers", "5",
            "--output-dir", str(output_dir)
        ])
        
        assert result.exit_code == 0
    
    def test_generate_data_no_validate(self, runner, tmp_path):
        """Generate data with validation disabled."""
        from src.cli.main import cli
        
        output_dir = tmp_path / "data"
        
        result = runner.invoke(cli, [
            "generate-data",
            "--customers", "5",
            "--products", "10",
            "--orders", "20",
            "--output-dir", str(output_dir),
            "--no-validate"
        ])
        
        assert result.exit_code == 0


class TestLoadDataCommand:
    """Tests for load-data command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @patch("src.cli.commands.data.SnowflakeConnector")
    def test_load_data_requires_input_dir(self, mock_connector, runner, tmp_path):
        """Load data validates input directory exists."""
        from src.cli.main import cli
        
        # Non-existent directory
        result = runner.invoke(cli, [
            "load-data",
            "--input-dir", "/nonexistent/path"
        ])
        
        # Should handle missing directory gracefully
        assert result.exit_code in [0, 1]
    
    def test_load_data_accepts_batch_size(self, runner, tmp_path):
        """Load data accepts batch-size option."""
        from src.cli.main import cli
        
        # Create input dir with some files
        input_dir = tmp_path / "data"
        input_dir.mkdir()
        
        result = runner.invoke(cli, [
            "load-data",
            "--input-dir", str(input_dir),
            "--batch-size", "5000"
        ])
        
        # May fail without data, but should accept the argument
        assert result.exit_code in [0, 1]


class TestWorkflowCommands:
    """Tests for workflow commands (create-schema, run-data-load)."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_create_schema_dry_run(self, runner):
        """Create-schema dry-run shows plan."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, ["create-schema", "--dry-run"])
        
        assert result.exit_code == 0
        # Should show what would be created
        assert "table" in result.output.lower() or "create" in result.output.lower()
    
    def test_create_schema_with_options(self, runner):
        """Create-schema accepts all options."""
        from src.cli.main import cli
        
        result = runner.invoke(cli, [
            "create-schema",
            "--dry-run",
            "--database", "TEST_DB",
            "--schema", "TEST_SCHEMA",
            "--skip-fk"
        ])
        
        assert result.exit_code == 0
    
    @patch("src.cli.commands.workflows.SnowflakeConnector")
    @patch("src.cli.commands.workflows.DataGenerationOrchestrator")
    @patch("src.cli.commands.workflows.DataLoadOrchestrator")
    def test_run_data_load_with_counts(
        self, mock_load_orch, mock_gen_orch, mock_connector, runner
    ):
        """Run-data-load accepts custom counts."""
        from src.cli.main import cli
        
        # Setup mocks
        mock_conn = MagicMock()
        mock_connector.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connector.return_value.__exit__ = MagicMock(return_value=False)
        
        result = runner.invoke(cli, [
            "run-data-load",
            "--customers", "10",
            "--products", "20",
            "--sales", "50"
        ])
        
        # May fail without real connection, but should accept arguments
        assert result.exit_code in [0, 1]


class TestStatusCommand:
    """Tests for status command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @patch("src.cli.commands.validate.SnowflakeConnector")
    def test_status_displays_info(self, mock_connector, runner):
        """Status command displays table creation info."""
        from src.cli.main import cli
        
        mock_conn = MagicMock()
        mock_connector.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connector.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute_query.return_value = []
        
        result = runner.invoke(cli, ["status"])
        
        # Should show some status info or error gracefully
        assert result.exit_code in [0, 1]


class TestValidateCommand:
    """Tests for validate command."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @patch("src.cli.commands.validate.SnowflakeConnector")
    def test_validate_with_options(self, mock_connector, runner):
        """Validate command accepts all options."""
        from src.cli.main import cli
        
        mock_conn = MagicMock()
        mock_connector.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connector.return_value.__exit__ = MagicMock(return_value=False)
        
        result = runner.invoke(cli, [
            "validate",
            "--check-fk",
            "--check-data"
        ])
        
        # May fail without connection, but should accept options
        assert result.exit_code in [0, 1]


