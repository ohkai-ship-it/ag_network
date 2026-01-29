"""Tests for validation utilities."""

import json
from pathlib import Path

from agnetwork.validate import (
    ValidationResult,
    validate_artifact_json,
    validate_json_file,
    validate_jsonl_file,
    validate_run_folder,
    validate_status_file,
    validate_worklog_file,
)


class TestJsonValidation:
    """Tests for JSON file validation."""

    def test_validate_valid_json(self, tmp_path: Path):
        """Test validation of valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value", "number": 42}')

        is_valid, data, error = validate_json_file(json_file)

        assert is_valid
        assert data == {"key": "value", "number": 42}
        assert error is None

    def test_validate_invalid_json(self, tmp_path: Path):
        """Test validation of invalid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{invalid json}")

        is_valid, data, error = validate_json_file(json_file)

        assert not is_valid
        assert data is None
        assert "Invalid JSON" in error

    def test_validate_missing_file(self, tmp_path: Path):
        """Test validation of non-existent file."""
        json_file = tmp_path / "nonexistent.json"

        is_valid, data, error = validate_json_file(json_file)

        assert not is_valid
        assert data is None
        assert "does not exist" in error


class TestJsonlValidation:
    """Tests for JSONL file validation."""

    def test_validate_valid_jsonl(self, tmp_path: Path):
        """Test validation of valid JSONL file."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"line": 1}\n{"line": 2}\n{"line": 3}\n')

        is_valid, lines, errors = validate_jsonl_file(jsonl_file)

        assert is_valid
        assert len(lines) == 3
        assert lines[0]["line"] == 1
        assert len(errors) == 0

    def test_validate_invalid_jsonl_line(self, tmp_path: Path):
        """Test validation catches invalid lines in JSONL."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"line": 1}\n{invalid}\n{"line": 3}\n')

        is_valid, lines, errors = validate_jsonl_file(jsonl_file)

        assert not is_valid
        assert len(lines) == 2  # Valid lines still parsed
        assert len(errors) == 1
        assert "Line 2" in errors[0]


class TestStatusFileValidation:
    """Tests for agent_status.json validation."""

    def test_validate_complete_status(self, tmp_path: Path):
        """Test validation of complete status file."""
        status_file = tmp_path / "agent_status.json"
        status_data = {
            "session_id": "test_123",
            "started_at": "2026-01-25T10:00:00",
            "last_updated": "2026-01-25T10:05:00",
            "current_phase": "1",
            "phases_completed": ["0"],
            "phases_in_progress": ["1"],
        }
        status_file.write_text(json.dumps(status_data))

        result = ValidationResult()
        data = validate_status_file(status_file, result)

        assert result.is_valid
        assert data is not None
        assert data["session_id"] == "test_123"

    def test_validate_incomplete_status(self, tmp_path: Path):
        """Test validation catches missing required keys."""
        status_file = tmp_path / "agent_status.json"
        status_data = {
            "session_id": "test_123",
            # Missing required keys
        }
        status_file.write_text(json.dumps(status_data))

        result = ValidationResult()
        validate_status_file(status_file, result)

        assert not result.is_valid
        assert any("Missing required keys" in str(e) for e in result.errors)


class TestWorklogValidation:
    """Tests for agent_worklog.jsonl validation."""

    def test_validate_complete_worklog(self, tmp_path: Path):
        """Test validation of complete worklog entries."""
        worklog_file = tmp_path / "agent_worklog.jsonl"
        entries = [
            {
                "timestamp": "2026-01-25T10:00:00",
                "phase": "1",
                "action": "Start",
                "status": "success",
            },
            {
                "timestamp": "2026-01-25T10:01:00",
                "phase": "1",
                "action": "Done",
                "status": "success",
            },
        ]
        worklog_file.write_text("\n".join(json.dumps(e) for e in entries))

        result = ValidationResult()
        parsed = validate_worklog_file(worklog_file, result)

        assert result.is_valid
        assert len(parsed) == 2

    def test_validate_incomplete_worklog_entry(self, tmp_path: Path):
        """Test validation catches entries missing required keys."""
        worklog_file = tmp_path / "agent_worklog.jsonl"
        entries = [
            {"timestamp": "2026-01-25T10:00:00", "phase": "1"},  # Missing action, status
        ]
        worklog_file.write_text("\n".join(json.dumps(e) for e in entries))

        result = ValidationResult()
        validate_worklog_file(worklog_file, result)

        assert not result.is_valid
        assert any("missing required keys" in str(e) for e in result.errors)


class TestArtifactValidation:
    """Tests for artifact JSON validation."""

    def test_validate_artifact_with_meta(self, tmp_path: Path):
        """Test validation of artifact with meta block."""
        artifact_file = tmp_path / "test_artifact.json"
        artifact_data = {
            "company": "TestCorp",
            "data": "test",
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "test_skill",
                "skill_version": "1.0",
                "generated_at": "2026-01-25T10:00:00",
                "run_id": "test_123",
            },
        }
        artifact_file.write_text(json.dumps(artifact_data))

        result = ValidationResult()
        data = validate_artifact_json(artifact_file, result, require_meta=True)

        assert result.is_valid
        assert data is not None

    def test_validate_artifact_missing_meta(self, tmp_path: Path):
        """Test validation warns about missing meta block."""
        artifact_file = tmp_path / "test_artifact.json"
        artifact_data = {"company": "TestCorp", "data": "test"}
        artifact_file.write_text(json.dumps(artifact_data))

        result = ValidationResult()
        validate_artifact_json(artifact_file, result, require_meta=True)

        # Should be a warning, not error (for backward compatibility)
        assert result.is_valid  # No errors
        assert len(result.warnings) > 0
        assert any("Missing 'meta'" in str(w) for w in result.warnings)


class TestRunFolderValidation:
    """Tests for complete run folder validation."""

    def test_validate_complete_run_folder(self, tmp_path: Path):
        """Test validation of a complete run folder."""
        run_dir = tmp_path / "20260125_100000__test__research"
        run_dir.mkdir()

        # Create structure
        (run_dir / "sources").mkdir()
        (run_dir / "artifacts").mkdir()
        (run_dir / "logs").mkdir()

        # Create status file
        status = {
            "session_id": "test",
            "started_at": "2026-01-25T10:00:00",
            "last_updated": "2026-01-25T10:00:00",
            "current_phase": "1",
            "phases_completed": [],
            "phases_in_progress": ["1"],
        }
        (run_dir / "logs" / "agent_status.json").write_text(json.dumps(status))

        # Create artifact
        artifact = {
            "company": "Test",
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "test",
                "skill_version": "1.0",
                "generated_at": "2026-01-25T10:00:00",
                "run_id": "test",
            },
        }
        (run_dir / "artifacts" / "test.json").write_text(json.dumps(artifact))
        (run_dir / "artifacts" / "test.md").write_text("# Test")

        result = validate_run_folder(run_dir, require_meta=True)

        assert result.is_valid, str(result)

    def test_validate_missing_status_file(self, tmp_path: Path):
        """Test validation catches missing status file."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        (run_dir / "logs").mkdir()
        (run_dir / "artifacts").mkdir()
        (run_dir / "sources").mkdir()

        result = validate_run_folder(run_dir)

        assert not result.is_valid
        assert any("Missing agent_status.json" in str(e) for e in result.errors)
