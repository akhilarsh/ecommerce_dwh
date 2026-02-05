"""
Tests for Snowflake connector.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import snowflake.connector
from snowflake.connector.errors import DatabaseError, ProgrammingError
from src.connectors.snowflake_connector import SnowflakeConnector


# Test Configuration
TEST_CONFIG = {
    "account": "test_account",
    "user": "test_user",
    "password": "test_password",
    "warehouse": "test_warehouse",
    "database": "test_database",
    "schema": "test_schema",
    "role": "test_role"
}


@pytest.fixture
def mock_snowflake_connection():
    """Mock Snowflake connection and cursor."""
    with patch('snowflake.connector.connect') as mock_connect:
        # Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        yield {
            'connect': mock_connect,
            'connection': mock_conn,
            'cursor': mock_cursor
        }


@pytest.fixture
def env_vars(monkeypatch):
    """Set up environment variables for testing."""
    for key, value in TEST_CONFIG.items():
        monkeypatch.setenv(f"SNOWFLAKE_{key.upper()}", value)
    return TEST_CONFIG


class TestSnowflakeConnectorInitialization:
    """Tests for SnowflakeConnector initialization."""
    
    def test_init_with_parameters(self):
        """Test initialization with explicit parameters."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        assert connector.account == TEST_CONFIG["account"]
        assert connector.user == TEST_CONFIG["user"]
        assert connector.password == TEST_CONFIG["password"]
        assert connector.warehouse == TEST_CONFIG["warehouse"]
        assert connector.database == TEST_CONFIG["database"]
        assert connector.schema == TEST_CONFIG["schema"]
        assert connector.role == TEST_CONFIG["role"]
    
    def test_init_with_environment_variables(self, env_vars):
        """Test initialization with environment variables."""
        connector = SnowflakeConnector()
        
        assert connector.account == env_vars["account"]
        assert connector.user == env_vars["user"]
        assert connector.password == env_vars["password"]
        assert connector.warehouse == env_vars["warehouse"]
        assert connector.database == env_vars["database"]
        assert connector.schema == env_vars["schema"]
        assert connector.role == env_vars["role"]
    
    def test_init_with_mixed_params_and_env(self, env_vars):
        """Test that explicit parameters override environment variables."""
        connector = SnowflakeConnector(
            account="override_account",
            user="override_user"
        )
        
        assert connector.account == "override_account"
        assert connector.user == "override_user"
        assert connector.password == env_vars["password"]  # From env
    
    def test_init_missing_account_raises_error(self):
        """Test that missing account raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SnowflakeConnector(user="test", password="test")
        
        assert "account" in str(exc_info.value)
    
    def test_init_missing_user_raises_error(self):
        """Test that missing user raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SnowflakeConnector(account="test", password="test")
        
        assert "user" in str(exc_info.value)
    
    def test_init_missing_password_raises_error(self):
        """Test that missing password raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SnowflakeConnector(account="test", user="test")
        
        assert "password" in str(exc_info.value)
    
    def test_init_missing_multiple_params_raises_error(self):
        """Test that missing multiple required base params raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SnowflakeConnector()
        
        error_msg = str(exc_info.value)
        # account and user are always required
        assert "account" in error_msg
        assert "user" in error_msg
        # password is only required for password authentication, not as a base requirement
    
    def test_init_optional_params_can_be_none(self):
        """Test that optional parameters can be None."""
        connector = SnowflakeConnector(
            account="test",
            user="test",
            password="test"
        )
        
        assert connector.warehouse is None
        assert connector.database is None
        assert connector.schema is None
        assert connector.role is None


class TestSnowflakeConnectorConnection:
    """Tests for connection management."""
    
    def test_connect_success(self, mock_snowflake_connection):
        """Test successful connection."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        # Verify connect was called with correct params
        mock_snowflake_connection['connect'].assert_called_once()
        call_kwargs = mock_snowflake_connection['connect'].call_args[1]
        
        assert call_kwargs['account'] == TEST_CONFIG['account']
        assert call_kwargs['user'] == TEST_CONFIG['user']
        assert call_kwargs['password'] == TEST_CONFIG['password']
        assert call_kwargs['warehouse'] == TEST_CONFIG['warehouse']
        assert call_kwargs['database'] == TEST_CONFIG['database']
        assert call_kwargs['schema'] == TEST_CONFIG['schema']
        assert call_kwargs['role'] == TEST_CONFIG['role']
        
        # Verify connection and cursor are set
        assert connector.connection is not None
        assert connector.cursor is not None
    
    def test_connect_without_optional_params(self, mock_snowflake_connection):
        """Test connection without optional parameters."""
        connector = SnowflakeConnector(
            account="test",
            user="test",
            password="test"
        )
        connector.connect()
        
        call_kwargs = mock_snowflake_connection['connect'].call_args[1]
        
        assert 'account' in call_kwargs
        assert 'user' in call_kwargs
        assert 'password' in call_kwargs
        assert 'warehouse' not in call_kwargs
        assert 'database' not in call_kwargs
        assert 'schema' not in call_kwargs
        assert 'role' not in call_kwargs
    
    def test_connect_failure_raises_error(self, mock_snowflake_connection):
        """Test that connection failure raises DatabaseError."""
        mock_snowflake_connection['connect'].side_effect = DatabaseError("Connection failed")
        
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(DatabaseError):
            connector.connect()
    
    def test_close_connection(self, mock_snowflake_connection):
        """Test closing connection."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        connector.close()
        
        mock_snowflake_connection['cursor'].close.assert_called_once()
        mock_snowflake_connection['connection'].close.assert_called_once()
    
    def test_close_without_connection(self):
        """Test closing without active connection."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        # Should not raise error
        connector.close()


class TestSnowflakeConnectorQueries:
    """Tests for query execution."""
    
    def test_execute_query_success(self, mock_snowflake_connection):
        """Test successful query execution."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        # Mock query results
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('col1',), ('col2',)]
        mock_cursor.fetchall.return_value = [('value1', 'value2'), ('value3', 'value4')]
        
        result = connector.execute_query("SELECT * FROM test_table")
        
        assert len(result) == 2
        assert result[0] == ('value1', 'value2')
        assert result[1] == ('value3', 'value4')
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test_table")
    
    def test_execute_query_with_params(self, mock_snowflake_connection):
        """Test query execution with parameters."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('col1',)]
        mock_cursor.fetchall.return_value = [('result',)]
        
        params = {"1": "value1", "2": "value2"}
        connector.execute_query("SELECT * FROM test WHERE col = %s", params)
        
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM test WHERE col = %s",
            params
        )
    
    def test_execute_query_no_results(self, mock_snowflake_connection):
        """Test query execution that returns no results."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = None  # No results
        
        result = connector.execute_query("INSERT INTO test VALUES (1, 2)")
        
        assert result == []
    
    def test_execute_query_without_connection_raises_error(self):
        """Test that executing query without connection raises error."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(RuntimeError) as exc_info:
            connector.execute_query("SELECT 1")
        
        assert "Not connected" in str(exc_info.value)
    
    def test_execute_query_sql_error_raises_exception(self, mock_snowflake_connection):
        """Test that SQL errors are raised."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.execute.side_effect = ProgrammingError("SQL syntax error")
        
        with pytest.raises(ProgrammingError):
            connector.execute_query("INVALID SQL")
    
    def test_execute_dict_success(self, mock_snowflake_connection):
        """Test execute_dict returns dictionaries."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        # Mock DictCursor
        mock_dict_cursor = MagicMock()
        mock_dict_cursor.description = [('col1',), ('col2',)]
        mock_dict_cursor.fetchall.return_value = [
            {'col1': 'value1', 'col2': 'value2'},
            {'col1': 'value3', 'col2': 'value4'}
        ]
        
        mock_conn = mock_snowflake_connection['connection']
        mock_conn.cursor.return_value = mock_dict_cursor
        
        result = connector.execute_dict("SELECT * FROM test_table")
        
        assert len(result) == 2
        assert result[0] == {'col1': 'value1', 'col2': 'value2'}
        assert result[1] == {'col1': 'value3', 'col2': 'value4'}
        mock_dict_cursor.close.assert_called_once()
    
    def test_execute_dict_with_params(self, mock_snowflake_connection):
        """Test execute_dict with parameters."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_dict_cursor = MagicMock()
        mock_dict_cursor.description = [('col1',)]
        mock_dict_cursor.fetchall.return_value = [{'col1': 'value'}]
        
        mock_conn = mock_snowflake_connection['connection']
        mock_conn.cursor.return_value = mock_dict_cursor
        
        params = {"1": "test"}
        connector.execute_dict("SELECT * FROM test WHERE id = %s", params)
        
        mock_dict_cursor.execute.assert_called_once_with(
            "SELECT * FROM test WHERE id = %s",
            params
        )
    
    def test_execute_dict_no_results(self, mock_snowflake_connection):
        """Test execute_dict with no results."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_dict_cursor = MagicMock()
        mock_dict_cursor.description = None
        
        mock_conn = mock_snowflake_connection['connection']
        mock_conn.cursor.return_value = mock_dict_cursor
        
        result = connector.execute_dict("INSERT INTO test VALUES (1)")
        
        assert result == []
    
    def test_execute_dict_without_connection_raises_error(self):
        """Test execute_dict without connection raises error."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(RuntimeError) as exc_info:
            connector.execute_dict("SELECT 1")
        
        assert "Not connected" in str(exc_info.value)
    
    def test_execute_many_success(self, mock_snowflake_connection):
        """Test batch execution."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        
        data = [(1, 'a'), (2, 'b'), (3, 'c')]
        connector.execute_many("INSERT INTO test VALUES (%s, %s)", data)
        
        mock_cursor.executemany.assert_called_once_with(
            "INSERT INTO test VALUES (%s, %s)",
            data
        )
    
    def test_execute_many_without_connection_raises_error(self):
        """Test execute_many without connection raises error."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(RuntimeError) as exc_info:
            connector.execute_many("INSERT INTO test VALUES (%s)", [(1,)])
        
        assert "Not connected" in str(exc_info.value)
    
    def test_execute_many_sql_error_raises_exception(self, mock_snowflake_connection):
        """Test that batch execution SQL errors are raised."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.executemany.side_effect = ProgrammingError("Batch insert failed")
        
        with pytest.raises(ProgrammingError):
            connector.execute_many("INSERT INTO test VALUES (%s)", [(1,)])


class TestSnowflakeConnectorTransactions:
    """Tests for transaction management."""
    
    def test_commit_success(self, mock_snowflake_connection):
        """Test successful commit."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        connector.commit()
        
        mock_snowflake_connection['connection'].commit.assert_called_once()
    
    def test_commit_without_connection_raises_error(self):
        """Test commit without connection raises error."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(RuntimeError) as exc_info:
            connector.commit()
        
        assert "Not connected" in str(exc_info.value)
    
    def test_rollback_success(self, mock_snowflake_connection):
        """Test successful rollback."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        connector.rollback()
        
        mock_snowflake_connection['connection'].rollback.assert_called_once()
    
    def test_rollback_without_connection_raises_error(self):
        """Test rollback without connection raises error."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        with pytest.raises(RuntimeError) as exc_info:
            connector.rollback()
        
        assert "Not connected" in str(exc_info.value)


class TestSnowflakeConnectorHelperMethods:
    """Tests for helper methods."""
    
    def test_get_current_database(self, mock_snowflake_connection):
        """Test getting current database."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('CURRENT_DATABASE()',)]
        mock_cursor.fetchall.return_value = [('TEST_DB',)]
        
        result = connector.get_current_database()
        
        assert result == 'TEST_DB'
        mock_cursor.execute.assert_called_with("SELECT CURRENT_DATABASE()")
    
    def test_get_current_database_none(self, mock_snowflake_connection):
        """Test getting current database when none set."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('CURRENT_DATABASE()',)]
        mock_cursor.fetchall.return_value = []
        
        result = connector.get_current_database()
        
        assert result is None
    
    def test_get_current_schema(self, mock_snowflake_connection):
        """Test getting current schema."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('CURRENT_SCHEMA()',)]
        mock_cursor.fetchall.return_value = [('TEST_SCHEMA',)]
        
        result = connector.get_current_schema()
        
        assert result == 'TEST_SCHEMA'
        mock_cursor.execute.assert_called_with("SELECT CURRENT_SCHEMA()")
    
    def test_table_exists_true(self, mock_snowflake_connection):
        """Test table_exists returns True when table exists."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('COUNT(*)',)]
        mock_cursor.fetchall.return_value = [(1,)]
        
        result = connector.table_exists("test_table")
        
        assert result is True
    
    def test_table_exists_false(self, mock_snowflake_connection):
        """Test table_exists returns False when table doesn't exist."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('COUNT(*)',)]
        mock_cursor.fetchall.return_value = [(0,)]
        
        result = connector.table_exists("non_existent_table")
        
        assert result is False
    
    def test_table_exists_with_schema(self, mock_snowflake_connection):
        """Test table_exists with explicit schema."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        connector.connect()
        
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('COUNT(*)',)]
        mock_cursor.fetchall.return_value = [(1,)]
        
        result = connector.table_exists("test_table", schema="custom_schema")
        
        assert result is True
        # Verify the query used the custom schema
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1]["1"] == "CUSTOM_SCHEMA"
    
    def test_table_exists_no_schema_raises_error(self, mock_snowflake_connection):
        """Test table_exists without schema raises error."""
        connector = SnowflakeConnector(
            account="test",
            user="test",
            password="test"
            # No schema provided
        )
        connector.connect()
        
        with pytest.raises(ValueError) as exc_info:
            connector.table_exists("test_table")
        
        assert "Schema must be provided" in str(exc_info.value)


class TestSnowflakeConnectorContextManager:
    """Tests for context manager functionality."""
    
    def test_context_manager_success(self, mock_snowflake_connection):
        """Test context manager with successful operations."""
        with SnowflakeConnector(**TEST_CONFIG) as conn:
            assert conn.connection is not None
            assert conn.cursor is not None
        
        # Verify connection was closed
        mock_snowflake_connection['cursor'].close.assert_called_once()
        mock_snowflake_connection['connection'].close.assert_called_once()
    
    def test_context_manager_with_exception(self, mock_snowflake_connection):
        """Test context manager with exception (should rollback)."""
        try:
            with SnowflakeConnector(**TEST_CONFIG) as conn:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify rollback and close were called
        mock_snowflake_connection['connection'].rollback.assert_called_once()
        mock_snowflake_connection['cursor'].close.assert_called_once()
        mock_snowflake_connection['connection'].close.assert_called_once()
    
    def test_context_manager_query_execution(self, mock_snowflake_connection):
        """Test executing queries within context manager."""
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('col1',)]
        mock_cursor.fetchall.return_value = [('value',)]
        
        with SnowflakeConnector(**TEST_CONFIG) as conn:
            result = conn.execute_query("SELECT 1")
        
        assert result == [('value',)]
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    def test_context_manager_connection_error(self, mock_snowflake_connection):
        """Test context manager with connection error."""
        mock_snowflake_connection['connect'].side_effect = DatabaseError("Connection failed")
        
        with pytest.raises(DatabaseError):
            with SnowflakeConnector(**TEST_CONFIG) as conn:
                pass


class TestSnowflakeConnectorIntegration:
    """Integration tests for common workflows."""
    
    def test_complete_query_workflow(self, mock_snowflake_connection):
        """Test complete workflow: connect, query, commit, close."""
        connector = SnowflakeConnector(**TEST_CONFIG)
        
        # Connect
        connector.connect()
        assert connector.connection is not None
        
        # Execute query
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = None
        connector.execute_query("INSERT INTO test VALUES (1)")
        
        # Commit
        connector.commit()
        mock_snowflake_connection['connection'].commit.assert_called_once()
        
        # Close
        connector.close()
        mock_cursor.close.assert_called_once()
    
    def test_context_manager_workflow(self, mock_snowflake_connection):
        """Test workflow using context manager."""
        mock_cursor = mock_snowflake_connection['cursor']
        mock_cursor.description = [('id',)]
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]
        
        with SnowflakeConnector(**TEST_CONFIG) as conn:
            # Query data
            results = conn.execute_query("SELECT id FROM test")
            assert len(results) == 3
            
            # Insert data
            mock_cursor.description = None
            conn.execute_query("INSERT INTO test VALUES (4)")
            
            # Commit handled automatically on exit
        
        # Connection closed automatically
        mock_cursor.close.assert_called_once()
    
    def test_error_recovery_workflow(self, mock_snowflake_connection):
        """Test error handling and recovery."""
        mock_cursor = mock_snowflake_connection['cursor']
        
        try:
            with SnowflakeConnector(**TEST_CONFIG) as conn:
                # Successful query
                mock_cursor.description = [('col1',)]
                mock_cursor.fetchall.return_value = [('value',)]
                result = conn.execute_query("SELECT * FROM test")
                assert result == [('value',)]
                
                # Failing query
                mock_cursor.execute.side_effect = ProgrammingError("SQL error")
                conn.execute_query("INVALID SQL")
        except ProgrammingError:
            pass
        
        # Rollback should have been called
        mock_snowflake_connection['connection'].rollback.assert_called_once()
        # Connection should be closed
        mock_cursor.close.assert_called_once()
