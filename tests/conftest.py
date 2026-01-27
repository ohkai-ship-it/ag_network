"""Test configuration and fixtures."""

import gc
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import pytest


def _close_loggers():
    """Close all loggers to release file handles (Windows compatibility)."""
    for logger_name in list(logging.Logger.manager.loggerDict):
        if logger_name.startswith("agnetwork."):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


@pytest.fixture
def temp_run_dir():
    """Provide a temporary directory for run tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
        _close_loggers()


@pytest.fixture
def temp_workspace_runs_dir() -> Generator[Path, None, None]:
    """Provide a temporary workspace and return its runs directory.

    This fixture patches WorkspaceRegistry so all CLI commands use the
    temporary workspace. Use this for CLI tests that need workspace isolation.
    """
    from agnetwork.workspaces.registry import WorkspaceRegistry

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_registry_root = Path(tmpdir)

        # Create a test workspace and set as default
        registry = WorkspaceRegistry(registry_root=temp_registry_root)
        test_ws = registry.create_workspace("test")
        registry.set_default_workspace("test")

        # Patch WorkspaceRegistry to use our temp directory
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        try:
            yield test_ws.runs_dir
        finally:
            WorkspaceRegistry.__init__ = original_init
            _close_loggers()
            gc.collect()


@pytest.fixture
def temp_config_runs_dir() -> Generator[Path, None, None]:
    """Provide a temporary runs directory via config patching.

    This fixture patches agnetwork.config.config.runs_dir directly.
    Use this for non-CLI tests that use KernelExecutor without workspace context.
    """
    import agnetwork.config

    original_runs_dir = agnetwork.config.config.runs_dir

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_path = Path(tmpdir)
        agnetwork.config.config.runs_dir = temp_path
        try:
            yield temp_path
        finally:
            agnetwork.config.config.runs_dir = original_runs_dir
            _close_loggers()
            gc.collect()
