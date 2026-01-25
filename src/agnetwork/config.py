"""Configuration and environment handling for BD Copilot."""

import os
from pathlib import Path

from dotenv import load_dotenv


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
            os.getenv("BD_DB_PATH", "data/bd.sqlite")
        )
        if not self.db_path.is_absolute():
            self.db_path = self.project_root / self.db_path

        # Runs directory
        self.runs_dir: Path = Path(
            os.getenv("BD_RUNS_DIR", "runs")
        )
        if not self.runs_dir.is_absolute():
            self.runs_dir = self.project_root / self.runs_dir

        # Logging
        self.log_level: str = os.getenv("BD_LOG_LEVEL", "INFO")

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
