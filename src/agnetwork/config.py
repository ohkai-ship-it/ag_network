"""Configuration and environment handling for AG Network."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class LLMConfig:
    """LLM-specific configuration."""

    def __init__(self):
        self.enabled: bool = os.getenv("AG_LLM_ENABLED", "0") == "1"
        self.default_provider: str = os.getenv("AG_LLM_DEFAULT_PROVIDER", "anthropic")
        self.default_model: str = os.getenv(
            "AG_LLM_DEFAULT_MODEL", "claude-sonnet-4-20250514"
        )
        self.temperature: float = float(os.getenv("AG_LLM_TEMPERATURE", "0.7"))
        self.max_tokens: int = int(os.getenv("AG_LLM_MAX_TOKENS", "4096"))
        self.timeout_s: int = int(os.getenv("AG_LLM_TIMEOUT_S", "60"))

        # Critic role (optional overrides)
        self.critic_provider: Optional[str] = os.getenv("AG_LLM_CRITIC_PROVIDER")
        self.critic_model: Optional[str] = os.getenv("AG_LLM_CRITIC_MODEL")

        # Draft role (optional overrides)
        self.draft_provider: Optional[str] = os.getenv("AG_LLM_DRAFT_PROVIDER")
        self.draft_model: Optional[str] = os.getenv("AG_LLM_DRAFT_MODEL")


class Config:
    """Central configuration object."""

    def __init__(self):
        # Load .env file if it exists
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Get project root
        self.project_root = Path(__file__).parent.parent.parent

        # Database
        self.db_path: Path = Path(
            os.getenv("AG_DB_PATH", "data/ag.sqlite")
        )
        if not self.db_path.is_absolute():
            self.db_path = self.project_root / self.db_path

        # Runs directory
        self.runs_dir: Path = Path(
            os.getenv("AG_RUNS_DIR", "runs")
        )
        if not self.runs_dir.is_absolute():
            self.runs_dir = self.project_root / self.runs_dir

        # Logging
        self.log_level: str = os.getenv("AG_LOG_LEVEL", "INFO")

        # LLM configuration
        self.llm = LLMConfig()

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
