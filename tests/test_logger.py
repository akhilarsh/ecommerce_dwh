"""
Tests for logger utility.
"""

import logging
import os
from pathlib import Path
import pytest
from src.utils.logger import setup_logger, get_logger


@pytest.fixture
def test_log_dir(tmp_path):
    """Create temporary log directory for testing."""
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir()
    return str(log_dir)


@pytest.fixture(autouse=True)
def cleanup_loggers():
    """Clean up logger handlers after each test."""
    yield
    # Remove all handlers from test loggers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if logger_name.startswith("logger_"):
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.setLevel(logging.NOTSET)


def test_logger_creates_log_file(test_log_dir):
    """Test that logger creates log file in specified directory."""
    logger = setup_logger(name="logger_file_creation", log_dir=test_log_dir)
    
    # Check log file was created
    log_files = list(Path(test_log_dir).glob("dwh_*.log"))
    assert len(log_files) == 1
    
    # Check filename format
    log_file = log_files[0]
    assert log_file.name.startswith("dwh_")
    assert log_file.name.endswith(".log")
    assert len(log_file.name) == 22  # dwh_MM-DD_HH:MM:SS.log
    # Verify format: MM-DD_HH:MM:SS
    timestamp_part = log_file.name[4:-4]  # Extract timestamp from dwh_XX-XX_XX:XX:XX.log
    assert "-" in timestamp_part
    assert timestamp_part.count(":") == 2


def test_logger_writes_to_file(test_log_dir):
    """Test that logger writes messages to log file."""
    logger = setup_logger(name="logger_file_write", log_dir=test_log_dir)
    
    test_message = "Test log message"
    logger.info(test_message)
    
    # Read log file
    log_files = list(Path(test_log_dir).glob("dwh_*.log"))
    assert len(log_files) == 1
    
    content = log_files[0].read_text()
    assert test_message in content
    assert "INFO" in content


def test_logger_respects_log_level(test_log_dir):
    """Test that logger respects log level."""
    logger = setup_logger(name="logger_level_filtering", log_level="WARNING", log_dir=test_log_dir)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    # Read log file
    log_files = list(Path(test_log_dir).glob("dwh_*.log"))
    content = log_files[0].read_text()
    
    # DEBUG and INFO should not be in file
    assert "Debug message" not in content
    assert "Info message" not in content
    
    # WARNING and ERROR should be in file
    assert "Warning message" in content
    assert "Error message" in content


def test_logger_uses_env_log_level(test_log_dir, monkeypatch):
    """Test that logger uses LOG_LEVEL from environment."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    logger = setup_logger(name="logger_env_config", log_dir=test_log_dir)
    
    assert logger.level == logging.DEBUG


def test_logger_has_both_handlers(test_log_dir):
    """Test that logger has both file and console handlers."""
    logger = setup_logger(name="logger_dual_handlers", log_dir=test_log_dir)
    
    assert len(logger.handlers) == 2
    
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "FileHandler" in handler_types
    assert "StreamHandler" in handler_types


def test_logger_avoids_duplicate_handlers(test_log_dir):
    """Test that calling setup_logger twice doesn't duplicate handlers."""
    logger1 = setup_logger(name="logger_no_duplication", log_dir=test_log_dir)
    logger2 = setup_logger(name="logger_no_duplication", log_dir=test_log_dir)
    
    assert logger1 is logger2
    assert len(logger1.handlers) == 2  # Should still have only 2 handlers


def test_get_logger_returns_existing(test_log_dir):
    """Test that get_logger returns existing logger."""
    logger1 = setup_logger(name="logger_retrieval_existing", log_dir=test_log_dir)
    logger2 = get_logger(name="logger_retrieval_existing")
    
    assert logger1 is logger2


def test_get_logger_creates_new_if_not_exists(test_log_dir):
    """Test that get_logger creates logger if it doesn't exist."""
    # Override default log_dir for this test
    import src.utils.logger as logger_module
    original_setup = logger_module.setup_logger
    
    def mock_setup(name="ecommerce_dwh", log_level=None, log_dir="logs"):
        return original_setup(name, log_level, test_log_dir)
    
    logger_module.setup_logger = mock_setup
    
    try:
        logger = get_logger(name="logger_retrieval_new")
        assert logger is not None
        assert len(logger.handlers) == 2
    finally:
        logger_module.setup_logger = original_setup


def test_log_format_includes_all_components(test_log_dir):
    """Test that log format includes timestamp, name, level, and message."""
    logger = setup_logger(name="logger_format_validation", log_dir=test_log_dir)
    
    logger.info("Format test message")
    
    log_files = list(Path(test_log_dir).glob("dwh_*.log"))
    content = log_files[0].read_text()
    
    # Check format components
    assert " - " in content  # Separator
    assert "logger_format_validation" in content  # Logger name
    assert "INFO" in content  # Log level
    assert "Format test message" in content  # Message
    # Timestamp format: YYYY-MM-DD HH:MM:SS
    assert content.count("-") >= 2  # Date separators
    assert content.count(":") >= 2  # Time separators


def test_logger_creates_directory_if_not_exists(tmp_path):
    """Test that logger creates log directory if it doesn't exist."""
    non_existent_dir = tmp_path / "new_logs"
    assert not non_existent_dir.exists()
    
    logger = setup_logger(name="logger_dir_creation", log_dir=str(non_existent_dir))
    
    assert non_existent_dir.exists()
    assert non_existent_dir.is_dir()
