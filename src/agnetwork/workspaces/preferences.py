"""Workspace preferences management.

Provides per-workspace preferences for language, tone, verbosity, and defaults.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Preferences:
    """Workspace preferences.

    Attributes:
        language: Preferred language (e.g., 'en', 'de')
        tone: Preferred tone (e.g., 'professional', 'casual', 'technical')
        verbosity: Output verbosity (e.g., 'concise', 'normal', 'detailed')
        privacy_mode: Privacy mode ('strict' or 'standard')
        default_channel: Default outreach channel ('email' or 'linkedin')
        default_template: Default sequence template name
    """

    language: str = "en"
    tone: str = "professional"
    verbosity: str = "normal"
    privacy_mode: str = "standard"
    default_channel: str = "email"
    default_template: Optional[str] = None

    @classmethod
    def load(cls, prefs_path: Path) -> Preferences:
        """Load preferences from JSON file.

        Args:
            prefs_path: Path to preferences JSON file

        Returns:
            Loaded Preferences instance
        """
        if not prefs_path.exists():
            return cls()  # Return defaults

        try:
            with open(prefs_path, "r") as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, TypeError):
            return cls()  # Return defaults on error

    def save(self, prefs_path: Path) -> None:
        """Save preferences to JSON file.

        Args:
            prefs_path: Path where to save preferences
        """
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "language": self.language,
            "tone": self.tone,
            "verbosity": self.verbosity,
            "privacy_mode": self.privacy_mode,
            "default_channel": self.default_channel,
            "default_template": self.default_template,
        }
        with open(prefs_path, "w") as f:
            json.dump(data, f, indent=2)

    def update(self, **kwargs) -> None:
        """Update preferences with provided values.

        Args:
            **kwargs: Preference key-value pairs to update
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> dict:
        """Convert preferences to dictionary.

        Returns:
            Dictionary representation of preferences
        """
        return {
            "language": self.language,
            "tone": self.tone,
            "verbosity": self.verbosity,
            "privacy_mode": self.privacy_mode,
            "default_channel": self.default_channel,
            "default_template": self.default_template,
        }

    @staticmethod
    def get_defaults() -> dict:
        """Get default preferences values.

        Returns:
            Dictionary of default preferences
        """
        return {
            "language": "en",
            "tone": "professional",
            "verbosity": "normal",
            "privacy_mode": "standard",
            "default_channel": "email",
            "default_template": None,
        }


class PreferencesManager:
    """Manages workspace preferences with CLI overrides."""

    def __init__(self, prefs_path: Path):
        """Initialize preferences manager.

        Args:
            prefs_path: Path to preferences file
        """
        self.prefs_path = prefs_path
        self._prefs = Preferences.load(prefs_path)
        self._overrides = {}

    def get(self, key: str, default=None):
        """Get a preference value.

        Resolution order:
        1. CLI override (if set)
        2. Workspace preference file
        3. Built-in default
        4. Provided default

        Args:
            key: Preference key
            default: Default value if not found

        Returns:
            Preference value
        """
        # Check overrides first
        if key in self._overrides:
            return self._overrides[key]

        # Check loaded preferences
        if hasattr(self._prefs, key):
            return getattr(self._prefs, key)

        # Fall back to provided default
        return default

    def set(self, key: str, value) -> None:
        """Set a preference value and save.

        Args:
            key: Preference key
            value: Preference value
        """
        if hasattr(self._prefs, key):
            setattr(self._prefs, key, value)
            self._prefs.save(self.prefs_path)

    def override(self, key: str, value) -> None:
        """Set a temporary override (not persisted).

        Args:
            key: Preference key
            value: Override value
        """
        self._overrides[key] = value

    def reset(self) -> None:
        """Reset preferences to defaults."""
        self._prefs = Preferences()
        self._prefs.save(self.prefs_path)

    def show(self) -> dict:
        """Get all current preference values.

        Returns:
            Dictionary of current preferences
        """
        result = self._prefs.to_dict()
        # Apply overrides
        result.update(self._overrides)
        return result
