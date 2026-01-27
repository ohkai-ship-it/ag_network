"""Workspace registry for managing multiple workspaces.

Provides discovery, creation, and management of workspaces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from agnetwork.workspaces.context import WorkspaceContext
from agnetwork.workspaces.manifest import WorkspaceManifest


class WorkspaceRegistry:
    """Registry for managing workspaces.

    Workspaces are stored in ~/.agnetwork/workspaces/ by default.
    Each workspace has its own directory with a workspace.toml manifest.
    """

    def __init__(self, registry_root: Optional[Path] = None):
        """Initialize workspace registry.

        Args:
            registry_root: Root directory for all workspaces.
                          Defaults to ~/.agnetwork/workspaces/
        """
        if registry_root is None:
            registry_root = Path.home() / ".agnetwork" / "workspaces"

        self.registry_root = Path(registry_root)
        self.registry_root.mkdir(parents=True, exist_ok=True)

        # Default workspace tracking file
        self.default_workspace_file = self.registry_root.parent / "default_workspace.txt"

    def create_workspace(
        self,
        name: str,
        root_dir: Optional[Path] = None,
        set_as_default: bool = False,
    ) -> WorkspaceContext:
        """Create a new workspace with manifest and directories.

        Args:
            name: Human-readable workspace name
            root_dir: Optional custom root directory. If not provided,
                     uses registry_root/<name>/
            set_as_default: Whether to set as default workspace

        Returns:
            Created WorkspaceContext

        Raises:
            ValueError: If workspace already exists
        """
        if root_dir is None:
            root_dir = self.registry_root / name

        root_dir = Path(root_dir).resolve()

        # Check if workspace already exists
        manifest_path = root_dir / "workspace.toml"
        if manifest_path.exists():
            raise ValueError(f"Workspace already exists: {name}")

        # Create workspace context
        context = WorkspaceContext.create(name=name, root_dir=root_dir)

        # Ensure directories exist
        context.ensure_directories()

        # Save manifest
        WorkspaceManifest.save(context, manifest_path)

        # Set as default if requested
        if set_as_default:
            self.set_default_workspace(name)

        return context

    def load_workspace(self, name: str) -> WorkspaceContext:
        """Load an existing workspace by name.

        Args:
            name: Workspace name

        Returns:
            Loaded WorkspaceContext

        Raises:
            FileNotFoundError: If workspace doesn't exist
        """
        workspace_dir = self.registry_root / name
        manifest_path = workspace_dir / "workspace.toml"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Workspace not found: {name}")

        return WorkspaceManifest.load(manifest_path)

    def list_workspaces(self) -> list[str]:
        """List all registered workspace names.

        Returns:
            List of workspace names
        """
        workspaces = []
        if not self.registry_root.exists():
            return workspaces

        for item in self.registry_root.iterdir():
            if item.is_dir():
                manifest_path = item / "workspace.toml"
                if manifest_path.exists():
                    workspaces.append(item.name)

        return sorted(workspaces)

    def workspace_exists(self, name: str) -> bool:
        """Check if a workspace exists.

        Args:
            name: Workspace name

        Returns:
            True if workspace exists
        """
        workspace_dir = self.registry_root / name
        manifest_path = workspace_dir / "workspace.toml"
        return manifest_path.exists()

    def get_default_workspace(self) -> Optional[str]:
        """Get the name of the default workspace.

        Returns:
            Default workspace name, or None if not set
        """
        if not self.default_workspace_file.exists():
            return None

        try:
            return self.default_workspace_file.read_text().strip()
        except Exception:
            return None

    def set_default_workspace(self, name: str) -> None:
        """Set the default workspace.

        Args:
            name: Workspace name to set as default

        Raises:
            ValueError: If workspace doesn't exist
        """
        if not self.workspace_exists(name):
            raise ValueError(f"Workspace does not exist: {name}")

        self.default_workspace_file.write_text(name)

    def get_or_create_default(self) -> WorkspaceContext:
        """Get default workspace or create 'default' workspace if none exists.

        Returns:
            WorkspaceContext for default workspace
        """
        default_name = self.get_default_workspace()

        if default_name and self.workspace_exists(default_name):
            return self.load_workspace(default_name)

        # Create default workspace
        if not self.workspace_exists("default"):
            context = self.create_workspace("default", set_as_default=True)
        else:
            context = self.load_workspace("default")
            self.set_default_workspace("default")

        return context

    def delete_workspace(self, name: str, confirm: bool = False) -> None:
        """Delete a workspace.

        Args:
            name: Workspace name to delete
            confirm: Must be True to actually delete

        Raises:
            ValueError: If workspace doesn't exist or confirm is False
        """
        if not confirm:
            raise ValueError("Must set confirm=True to delete workspace")

        if not self.workspace_exists(name):
            raise ValueError(f"Workspace does not exist: {name}")

        workspace_dir = self.registry_root / name

        # Remove all files
        import shutil

        shutil.rmtree(workspace_dir)

        # Clear default if this was it
        if self.get_default_workspace() == name:
            if self.default_workspace_file.exists():
                self.default_workspace_file.unlink()

    def get_workspace_info(self, name: str) -> dict:
        """Get information about a workspace.

        Args:
            name: Workspace name

        Returns:
            Dictionary with workspace information

        Raises:
            FileNotFoundError: If workspace doesn't exist
        """
        context = self.load_workspace(name)
        manifest_path = context.root_dir / "workspace.toml"
        policy = WorkspaceManifest.load_policy(manifest_path)

        return {
            "name": context.name,
            "workspace_id": context.workspace_id,
            "root_dir": str(context.root_dir),
            "paths": {
                "runs": str(context.runs_dir),
                "db": str(context.db_path),
                "prefs": str(context.prefs_path),
                "exports": str(context.exports_dir),
                "sources_cache": str(context.sources_cache_dir),
            },
            "paths_exist": context.verify_paths(),
            "policy": policy,
            "is_default": self.get_default_workspace() == name,
        }
