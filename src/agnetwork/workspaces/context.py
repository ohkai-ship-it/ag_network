"""Workspace context and configuration for AG Network.

Provides workspace isolation and scoped storage/runs/preferences.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class WorkspaceContext:
    """Context for a workspace with isolated storage and configuration.

    Attributes:
        name: Human-readable workspace name
        workspace_id: Stable unique identifier (UUID or hash)
        root_dir: Root directory for this workspace
        runs_dir: Directory for run outputs (derived from root)
        db_path: Path to SQLite database (derived from root)
        prefs_path: Path to preferences file (derived from root)
        exports_dir: Directory for CRM exports (derived from root)
        sources_cache_dir: Directory for cached web sources (derived from root)
    """

    name: str
    workspace_id: str
    root_dir: Path
    runs_dir: Path = field(init=False)
    db_path: Path = field(init=False)
    prefs_path: Path = field(init=False)
    exports_dir: Path = field(init=False)
    sources_cache_dir: Path = field(init=False)

    def __post_init__(self):
        """Derive paths from root directory."""
        self.root_dir = Path(self.root_dir).resolve()
        self.runs_dir = self.root_dir / "runs"
        self.db_path = self.root_dir / "db" / "workspace.sqlite"
        self.prefs_path = self.root_dir / "prefs.json"
        self.exports_dir = self.root_dir / "exports"
        self.sources_cache_dir = self.root_dir / "sources_cache"

    @classmethod
    def create(
        cls,
        name: str,
        root_dir: Path,
        workspace_id: Optional[str] = None,
    ) -> WorkspaceContext:
        """Create a new workspace context.

        Args:
            name: Human-readable workspace name
            root_dir: Root directory for workspace
            workspace_id: Optional stable ID (generates UUID if not provided)

        Returns:
            New WorkspaceContext instance
        """
        if workspace_id is None:
            # Generate stable ID from name for repeatability
            workspace_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

        return cls(
            name=name,
            workspace_id=workspace_id,
            root_dir=root_dir,
        )

    def ensure_directories(self) -> None:
        """Create all necessary directories for this workspace."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.sources_cache_dir.mkdir(parents=True, exist_ok=True)

    def verify_paths(self) -> dict[str, bool]:
        """Verify that all workspace paths exist.

        Returns:
            Dictionary mapping path names to existence status
        """
        return {
            "root_dir": self.root_dir.exists(),
            "runs_dir": self.runs_dir.exists(),
            "db_dir": self.db_path.parent.exists(),
            "exports_dir": self.exports_dir.exists(),
            "sources_cache_dir": self.sources_cache_dir.exists(),
        }

    def get_db_path(self) -> Path:
        """Get the database path for this workspace.

        Returns:
            Path to workspace database
        """
        return self.db_path

    def get_runs_dir(self) -> Path:
        """Get the runs directory for this workspace.

        Returns:
            Path to runs directory
        """
        return self.runs_dir

    def get_exports_dir(self) -> Path:
        """Get the exports directory for this workspace.

        Returns:
            Path to exports directory
        """
        return self.exports_dir

    def __repr__(self) -> str:
        """String representation of workspace context."""
        return (
            f"WorkspaceContext(name={self.name!r}, "
            f"workspace_id={self.workspace_id!r}, "
            f"root_dir={self.root_dir})"
        )


class WorkspaceMismatchError(Exception):
    """Raised when a workspace ID mismatch is detected."""

    def __init__(self, expected: str, actual: str):
        """Initialize error with workspace IDs.

        Args:
            expected: Expected workspace ID
            actual: Actual workspace ID found
        """
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Workspace mismatch: expected {expected!r}, found {actual!r}. "
            f"Cannot use database from different workspace."
        )
