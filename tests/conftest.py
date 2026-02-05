"""
Pytest configuration and fixtures.

Creates test-specific log files for all test runs.
"""

import logging
from datetime import datetime
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Setup logging for test sessions."""
    # Create logs directory if not exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Generate timestamped test log filename
    timestamp = datetime.now().strftime("%m-%d_%H:%M:%S")
    log_file = log_dir / f"test_run_{timestamp}.log"
    
    # Configure root logger for tests
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ],
        force=True
    )
    
    logger = logging.getLogger("test_session")
    logger.info(f"Test session started. Log file: {log_file}")
    
    yield
    
    logger.info("Test session completed")


@pytest.fixture(autouse=True)
def log_test_execution(request):
    """Automatically log start and completion of each test."""
    logger = logging.getLogger("test_execution")
    test_name = request.node.name
    
    logger.info(f"▶ Starting test: {test_name}")
    
    yield
    
    # Check test outcome
    if hasattr(request.node, 'rep_call'):
        if request.node.rep_call.passed:
            logger.info(f"✓ Test passed: {test_name}")
        elif request.node.rep_call.failed:
            logger.error(f"✗ Test failed: {test_name}")
    else:
        logger.info(f"✓ Test completed: {test_name}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test outcome for logging."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
