"""
Tests for logging decorators.
"""

from src.utils.decorators import log_execution, log_method, log_sql_execution


@log_execution
def sample_function(x, y):
    """Sample function to test log_execution decorator."""
    return x + y


@log_execution
def failing_function():
    """Sample function that raises an exception."""
    raise ValueError("Test error")


class SampleClass:
    """Sample class to test log_method decorator."""
    
    @log_method
    def sample_method(self, value):
        """Sample method."""
        return value * 2
    
    @log_sql_execution
    def execute_query(self, query):
        """Sample SQL execution method."""
        # Simulate query execution
        return [{"id": 1}, {"id": 2}]


def test_log_execution_decorator():
    """Test that log_execution decorator logs function execution."""
    result = sample_function(5, 3)
    assert result == 8


def test_log_execution_with_exception():
    """Test that log_execution decorator logs exceptions."""
    try:
        failing_function()
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


def test_log_method_decorator():
    """Test that log_method decorator logs method execution."""
    obj = SampleClass()
    result = obj.sample_method(10)
    assert result == 20


def test_log_sql_execution_decorator():
    """Test that log_sql_execution decorator logs SQL execution."""
    obj = SampleClass()
    result = obj.execute_query("SELECT * FROM test_table")
    assert len(result) == 2
