"""Run management and logging for BD Copilot."""

import json
import logging
import logging.handlers
from datetime import datetime
from typing import Any, Dict, Optional

from bdcopilot.config import config


class RunManager:
    """Manages run folders and logging."""

    def __init__(self, command: str, slug: str):
        """Initialize a new run session."""
        self.command = command
        self.slug = slug
        self.timestamp = datetime.utcnow()
        self.run_id = f"{self.timestamp.strftime('%Y%m%d_%H%M%S')}__{slug}__{command}"
        self.run_dir = config.runs_dir / self.run_id

        # Create run directory structure
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "sources").mkdir(exist_ok=True)
        (self.run_dir / "artifacts").mkdir(exist_ok=True)
        (self.run_dir / "logs").mkdir(exist_ok=True)

        # Initialize logging
        self.logger = self._setup_logger()
        self.worklog_path = self.run_dir / "logs" / "agent_worklog.jsonl"
        self.status_path = self.run_dir / "logs" / "agent_status.json"

        # Initialize status file
        self._init_status()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for this run."""
        logger = logging.getLogger(f"bdcopilot.{self.run_id}")
        logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # File handler
        log_file = self.run_dir / "logs" / "run.log"
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def _init_status(self) -> None:
        """Initialize agent status file."""
        status = {
            "session_id": self.run_id,
            "started_at": self.timestamp.isoformat(),
            "last_updated": self.timestamp.isoformat(),
            "current_phase": "0",
            "phases_completed": [],
            "phases_in_progress": ["0"],
            "phases_blocked": [],
            "issues_fixed": [],
            "issues_remaining": [],
            "metrics": {
                "tests_passing": 0,
                "lint_status": "not_run",
                "coverage": 0.0,
            },
        }
        with open(self.status_path, "w") as f:
            json.dump(status, f, indent=2)

    def log_action(
        self,
        phase: str,
        action: str,
        status: str,
        changes_made: Optional[list] = None,
        tests_run: Optional[list] = None,
        verification_results: Optional[dict] = None,
        next_action: Optional[str] = None,
        issues_discovered: Optional[list] = None,
    ) -> None:
        """Log an action to the worklog."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": phase,
            "action": action,
            "status": status,
            "changes_made": changes_made or [],
            "tests_run": tests_run or [],
            "verification_results": verification_results or {},
            "next_action": next_action,
            "issues_discovered": issues_discovered or [],
        }

        with open(self.worklog_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        self.logger.info(f"[{phase}] {action} - {status}")

    def save_inputs(self, inputs: Dict[str, Any]) -> None:
        """Save command inputs to inputs.json."""
        inputs_file = self.run_dir / "inputs.json"
        with open(inputs_file, "w") as f:
            json.dump(inputs, f, indent=2, default=str)

    def save_artifact(
        self, artifact_name: str, markdown_content: str, json_data: Dict[str, Any]
    ) -> None:
        """Save both markdown and JSON versions of an artifact."""
        md_file = self.run_dir / "artifacts" / f"{artifact_name}.md"
        json_file = self.run_dir / "artifacts" / f"{artifact_name}.json"

        with open(md_file, "w") as f:
            f.write(markdown_content)

        with open(json_file, "w") as f:
            json.dump(json_data, f, indent=2, default=str)

        self.logger.info(f"Saved artifact: {artifact_name}")

    def update_status(self, **kwargs) -> None:
        """Update agent status file."""
        with open(self.status_path, "r") as f:
            status = json.load(f)

        for key, value in kwargs.items():
            if key in status:
                status[key] = value

        status["last_updated"] = datetime.utcnow().isoformat()

        with open(self.status_path, "w") as f:
            json.dump(status, f, indent=2)
