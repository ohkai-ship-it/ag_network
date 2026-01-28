"""Validation utilities for run folders and logging.

M4 additions:
- Claim evidence validation
- Source existence checks
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from agnetwork.workspaces.context import WorkspaceContext

# Required keys for agent_status.json
REQUIRED_STATUS_KEYS = {
    "session_id",
    "started_at",
    "last_updated",
    "current_phase",
    "phases_completed",
    "phases_in_progress",
}

# Required keys for agent_worklog.jsonl entries
REQUIRED_WORKLOG_KEYS = {
    "timestamp",
    "phase",
    "action",
    "status",
}

# Required keys in artifact meta block
REQUIRED_META_KEYS = {
    "artifact_version",
    "skill_name",
    "skill_version",
    "generated_at",
    "run_id",
}


class ValidationError:
    """Represents a single validation error."""

    def __init__(self, file_path: str, message: str, line: Optional[int] = None):
        self.file_path = file_path
        self.message = message
        self.line = line

    def __str__(self) -> str:
        if self.line is not None:
            return f"{self.file_path}:{self.line}: {self.message}"
        return f"{self.file_path}: {self.message}"


class ValidationResult:
    """Result of a validation operation."""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, file_path: str, message: str, line: Optional[int] = None) -> None:
        self.errors.append(ValidationError(file_path, message, line))

    def add_warning(self, file_path: str, message: str, line: Optional[int] = None) -> None:
        self.warnings.append(ValidationError(file_path, message, line))

    def __str__(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  ❌ {err}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  ⚠️  {warn}")
        if self.is_valid and not self.warnings:
            lines.append("✅ Validation passed")
        return "\n".join(lines)


def validate_json_file(file_path: Path) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Validate that a file contains valid JSON.

    Returns:
        Tuple of (is_valid, parsed_data, error_message)
    """
    if not file_path.exists():
        return False, None, f"File does not exist: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return True, data, None
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {e}"
    except Exception as e:
        return False, None, f"Error reading file: {e}"


def validate_jsonl_file(file_path: Path) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    """Validate that a file contains valid JSONL (JSON Lines).

    Returns:
        Tuple of (is_valid, parsed_lines, error_messages)
    """
    if not file_path.exists():
        return False, [], [f"File does not exist: {file_path}"]

    lines = []
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                try:
                    data = json.loads(line)
                    lines.append(data)
                except json.JSONDecodeError as e:
                    errors.append(f"Line {i}: Invalid JSON - {e}")
    except Exception as e:
        return False, [], [f"Error reading file: {e}"]

    return len(errors) == 0, lines, errors


def validate_status_file(file_path: Path, result: ValidationResult) -> Optional[Dict[str, Any]]:
    """Validate agent_status.json file.

    Args:
        file_path: Path to agent_status.json
        result: ValidationResult to add errors/warnings to

    Returns:
        Parsed data if valid, None otherwise
    """
    is_valid, data, error = validate_json_file(file_path)

    if not is_valid:
        result.add_error(str(file_path), error or "Unknown error")
        return None

    # Check required keys
    missing_keys = REQUIRED_STATUS_KEYS - set(data.keys())
    if missing_keys:
        result.add_error(str(file_path), f"Missing required keys: {missing_keys}")

    return data


def validate_worklog_file(file_path: Path, result: ValidationResult) -> List[Dict[str, Any]]:
    """Validate agent_worklog.jsonl file.

    Args:
        file_path: Path to agent_worklog.jsonl
        result: ValidationResult to add errors/warnings to

    Returns:
        List of parsed entries
    """
    is_valid, entries, errors = validate_jsonl_file(file_path)

    for error in errors:
        result.add_error(str(file_path), error)

    # Validate each entry has required keys
    for i, entry in enumerate(entries, 1):
        missing_keys = REQUIRED_WORKLOG_KEYS - set(entry.keys())
        if missing_keys:
            result.add_error(str(file_path), f"Entry {i} missing required keys: {missing_keys}")

    return entries


def validate_artifact_json(
    file_path: Path, result: ValidationResult, require_meta: bool = True
) -> Optional[Dict[str, Any]]:
    """Validate an artifact JSON file.

    Args:
        file_path: Path to artifact JSON file
        result: ValidationResult to add errors/warnings to
        require_meta: Whether to require meta block (False for legacy artifacts)

    Returns:
        Parsed data if valid, None otherwise
    """
    is_valid, data, error = validate_json_file(file_path)

    if not is_valid:
        result.add_error(str(file_path), error or "Unknown error")
        return None

    # Check for meta block
    if require_meta:
        if "meta" not in data:
            result.add_warning(
                str(file_path), "Missing 'meta' block (may be legacy artifact)"
            )
        else:
            meta = data["meta"]
            missing_keys = REQUIRED_META_KEYS - set(meta.keys())
            if missing_keys:
                result.add_error(
                    str(file_path), f"Meta block missing required keys: {missing_keys}"
                )

    return data


def _validate_logs_dir(logs_dir: Path, result: ValidationResult) -> None:
    """Validate the logs directory of a run."""
    status_file = logs_dir / "agent_status.json"
    if status_file.exists():
        validate_status_file(status_file, result)
    else:
        result.add_error(str(logs_dir), "Missing agent_status.json")

    worklog_file = logs_dir / "agent_worklog.jsonl"
    if worklog_file.exists():
        validate_worklog_file(worklog_file, result)
    # worklog may not exist if no actions logged yet


def _validate_artifacts_dir(
    artifacts_dir: Path, result: ValidationResult, require_meta: bool
) -> None:
    """Validate the artifacts directory of a run."""
    for json_file in artifacts_dir.glob("*.json"):
        validate_artifact_json(json_file, result, require_meta=require_meta)

    # Check that each .json has a corresponding .md
    for json_file in artifacts_dir.glob("*.json"):
        md_file = json_file.with_suffix(".md")
        if not md_file.exists():
            result.add_warning(
                str(json_file), f"Missing corresponding markdown file: {md_file.name}"
            )


def validate_run_folder(
    run_path: Path,
    require_meta: bool = False,
    check_evidence: bool = False,
    ws_ctx: Optional["WorkspaceContext"] = None,
) -> ValidationResult:
    """Validate an entire run folder for integrity.

    Args:
        run_path: Path to run folder
        require_meta: Whether to require meta blocks in artifacts
        check_evidence: Whether to check claim evidence (M4)
        ws_ctx: Optional WorkspaceContext for database access (required for check_evidence)

    Returns:
        ValidationResult with all errors and warnings
    """
    result = ValidationResult()

    if not run_path.exists():
        result.add_error(str(run_path), "Run folder does not exist")
        return result

    if not run_path.is_dir():
        result.add_error(str(run_path), "Path is not a directory")
        return result

    # Check required subdirectories
    for subdir in ["logs", "artifacts", "sources"]:
        subdir_path = run_path / subdir
        if not subdir_path.exists():
            result.add_warning(str(run_path), f"Missing subdirectory: {subdir}")

    # Validate logs
    logs_dir = run_path / "logs"
    if logs_dir.exists():
        _validate_logs_dir(logs_dir, result)

    # Validate artifacts
    artifacts_dir = run_path / "artifacts"
    if artifacts_dir.exists():
        _validate_artifacts_dir(artifacts_dir, result, require_meta)

    # M4: Validate claim evidence if requested
    if check_evidence:
        _validate_claim_evidence(run_path, result, ws_ctx)

    return result


def _validate_claim_evidence(
    run_path: Path,
    result: ValidationResult,
    ws_ctx: Optional["WorkspaceContext"] = None,
) -> None:
    """Validate claim evidence consistency (M4).

    Checks that:
    - Artifacts referenced by claims exist
    - Sources referenced in claims exist in DB

    This is a lightweight check that doesn't fail for manual runs.

    Args:
        run_path: Path to run folder
        result: ValidationResult to add errors/warnings to
        ws_ctx: Optional WorkspaceContext for database access
    """
    from agnetwork.storage.sqlite import SQLiteManager, normalize_source_ids

    if ws_ctx is None:
        result.add_warning(
            str(run_path),
            "Cannot validate claim evidence: no workspace context provided"
        )
        return

    try:
        db = SQLiteManager.for_workspace(ws_ctx)
    except Exception as e:
        result.add_warning(str(run_path), f"Cannot connect to database: {e}")
        return

    # Extract run_id from path
    run_id = run_path.name

    # Get artifacts for this run
    artifacts = db.get_artifacts_by_run(run_id)

    # Check claims for each artifact
    for artifact in artifacts:
        claims = db.get_claims_by_artifact(artifact["id"])

        for claim in claims:
            # Check source_ids exist
            source_ids = normalize_source_ids(claim.get("source_ids"))

            for source_id in source_ids:
                if not db.source_exists(source_id):
                    result.add_warning(
                        str(run_path),
                        f"Claim references non-existent source: {source_id}",
                    )
