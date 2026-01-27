"""Workspace manifest loading and management.

Handles workspace.toml manifest files for workspace configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # fallback for Python 3.10

import toml

from agnetwork.workspaces.context import WorkspaceContext


class WorkspaceManifest:
    """Manages workspace manifest (workspace.toml) loading and saving."""

    @staticmethod
    def load(manifest_path: Path) -> WorkspaceContext:
        """Load workspace context from manifest file.

        Args:
            manifest_path: Path to workspace.toml file

        Returns:
            WorkspaceContext loaded from manifest

        Raises:
            FileNotFoundError: If manifest doesn't exist
            ValueError: If manifest is invalid
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Workspace manifest not found: {manifest_path}")

        with open(manifest_path, "rb") as f:
            data = tomllib.load(f)

        # Validate required sections
        if "workspace" not in data:
            raise ValueError("Manifest missing [workspace] section")

        ws_section = data["workspace"]
        name = ws_section.get("name")
        workspace_id = ws_section.get("workspace_id")

        if not name:
            raise ValueError("Manifest missing workspace.name")
        if not workspace_id:
            raise ValueError("Manifest missing workspace.workspace_id")

        # Root directory is parent of manifest file
        root_dir = manifest_path.parent

        # Create context (will derive paths)
        return WorkspaceContext(
            name=name,
            workspace_id=workspace_id,
            root_dir=root_dir,
        )

    @staticmethod
    def save(context: WorkspaceContext, manifest_path: Path) -> None:
        """Save workspace context to manifest file.

        Args:
            context: WorkspaceContext to save
            manifest_path: Path where to save workspace.toml
        """
        data = {
            "workspace": {
                "name": context.name,
                "workspace_id": context.workspace_id,
            },
            "paths": {
                "runs": "runs",
                "db": "db/workspace.sqlite",
                "prefs": "prefs.json",
                "exports": "exports",
                "sources_cache": "sources_cache",
            },
            "policy": {
                "privacy_mode": "standard",
                "allow_web_fetch": True,
                "allow_memory": True,
            },
        }

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            toml.dump(data, f)

    @staticmethod
    def load_policy(manifest_path: Path) -> dict:
        """Load policy section from manifest.

        Args:
            manifest_path: Path to workspace.toml file

        Returns:
            Policy dictionary with defaults for missing values
        """
        if not manifest_path.exists():
            return {
                "privacy_mode": "standard",
                "allow_web_fetch": True,
                "allow_memory": True,
            }

        with open(manifest_path, "rb") as f:
            data = tomllib.load(f)

        policy = data.get("policy", {})
        return {
            "privacy_mode": policy.get("privacy_mode", "standard"),
            "allow_web_fetch": policy.get("allow_web_fetch", True),
            "allow_memory": policy.get("allow_memory", True),
        }

    @staticmethod
    def update_policy(manifest_path: Path, **policy_updates) -> None:
        """Update policy section in manifest.

        Args:
            manifest_path: Path to workspace.toml file
            **policy_updates: Policy fields to update
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Workspace manifest not found: {manifest_path}")

        with open(manifest_path, "rb") as f:
            data = tomllib.load(f)

        if "policy" not in data:
            data["policy"] = {}

        data["policy"].update(policy_updates)

        with open(manifest_path, "w") as f:
            toml.dump(data, f)
