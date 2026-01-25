"""Test configuration and fixtures."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def temp_run_dir():
    """Provide a temporary directory for run tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
        # Close all loggers to release file handles
        for logger_name in list(logging.Logger.manager.loggerDict):
            logger = logging.getLogger(logger_name)
            if logger.hasHandlers():
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)
