"""Policy enforcement for workspaces.

Enforces workspace-level policies for memory, web fetch, and privacy.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agnetwork.workspaces import WorkspaceContext


class PolicyViolationError(Exception):
    """Raised when a workspace policy is violated."""

    pass


class Policy:
    """Workspace policy enforcement.

    Attributes:
        allow_memory: Whether memory retrieval is allowed
        allow_web_fetch: Whether web fetching is allowed
        privacy_mode: Privacy mode ('strict' or 'standard')
    """

    def __init__(
        self,
        allow_memory: bool = True,
        allow_web_fetch: bool = True,
        privacy_mode: str = "standard",
    ):
        """Initialize policy.

        Args:
            allow_memory: Whether memory retrieval is allowed
            allow_web_fetch: Whether web fetching is allowed
            privacy_mode: Privacy mode ('strict' or 'standard')
        """
        self.allow_memory = allow_memory
        self.allow_web_fetch = allow_web_fetch
        self.privacy_mode = privacy_mode

    @classmethod
    def from_manifest(cls, manifest_path: Path) -> Policy:
        """Load policy from workspace manifest.

        Args:
            manifest_path: Path to workspace.toml

        Returns:
            Policy instance
        """
        from agnetwork.workspaces.manifest import WorkspaceManifest

        policy_data = WorkspaceManifest.load_policy(manifest_path)
        return cls(
            allow_memory=policy_data.get("allow_memory", True),
            allow_web_fetch=policy_data.get("allow_web_fetch", True),
            privacy_mode=policy_data.get("privacy_mode", "standard"),
        )

    @classmethod
    def from_workspace(cls, workspace: WorkspaceContext) -> Policy:
        """Load policy from workspace context.

        Args:
            workspace: WorkspaceContext

        Returns:
            Policy instance
        """
        manifest_path = workspace.root_dir / "workspace.toml"
        return cls.from_manifest(manifest_path)

    def enforce_memory(self, use_memory: bool) -> None:
        """Enforce memory policy.

        Args:
            use_memory: Whether memory is requested

        Raises:
            PolicyViolationError: If memory is requested but not allowed
        """
        if use_memory and not self.allow_memory:
            raise PolicyViolationError(
                "Memory retrieval is disabled for this workspace. "
                "Update workspace policy to enable."
            )

    def enforce_web_fetch(self, urls: list[str]) -> None:
        """Enforce web fetch policy.

        Args:
            urls: List of URLs to fetch

        Raises:
            PolicyViolationError: If web fetch is requested but not allowed
        """
        if urls and not self.allow_web_fetch:
            raise PolicyViolationError(
                "Web fetching is disabled for this workspace. Update workspace policy to enable."
            )

    def is_strict_privacy(self) -> bool:
        """Check if privacy mode is strict.

        Returns:
            True if privacy mode is strict
        """
        return self.privacy_mode == "strict"

    def to_dict(self) -> dict:
        """Convert policy to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "allow_memory": self.allow_memory,
            "allow_web_fetch": self.allow_web_fetch,
            "privacy_mode": self.privacy_mode,
        }
