"""PR1: Storage enforcement tests.

Tests that verify workspace isolation is enforced at the storage layer:
- SQLiteManager requires explicit db_path and workspace_id
- SQLiteManager.for_workspace() factory works correctly
- CRMStorage requires explicit db_path
- No parameterless SQLiteManager() calls exist in src/
"""

import ast
from pathlib import Path

import pytest

from agnetwork.crm.storage import CRMStorage
from agnetwork.storage.sqlite import SQLiteManager
from agnetwork.workspaces import WorkspaceContext, WorkspaceMismatchError


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace context."""
    ws_root = tmp_path / "test_workspace"
    ws_root.mkdir()
    return WorkspaceContext.create(
        name="test_workspace",
        root_dir=ws_root,
        workspace_id="test-workspace-id-123",
    )


@pytest.fixture
def another_workspace(tmp_path):
    """Create another temporary workspace context."""
    ws_root = tmp_path / "another_workspace"
    ws_root.mkdir()
    return WorkspaceContext.create(
        name="another_workspace",
        root_dir=ws_root,
        workspace_id="another-workspace-id-456",
    )


class TestSQLiteManagerEnforcement:
    """Test SQLiteManager workspace enforcement."""

    def test_sqlite_init_requires_db_path(self):
        """SQLiteManager() without db_path should raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            SQLiteManager(None)
        assert "requires explicit db_path" in str(exc_info.value)

    def test_sqlite_for_workspace_factory_creates_instance(self, temp_workspace):
        """SQLiteManager.for_workspace() should create a workspace-bound instance."""
        temp_workspace.ensure_directories()
        db = SQLiteManager.for_workspace(temp_workspace)
        assert db is not None
        assert db.db_path == temp_workspace.db_path
        db.close()

    def test_sqlite_for_workspace_factory_verifies_id(self, temp_workspace):
        """SQLiteManager.for_workspace() should auto-verify workspace ID."""
        temp_workspace.ensure_directories()
        db = SQLiteManager.for_workspace(temp_workspace)

        # The workspace_id should be set in the database
        stored_id = db.get_workspace_id()
        assert stored_id == temp_workspace.workspace_id
        db.close()

    def test_sqlite_for_workspace_factory_initializes_new_db(self, temp_workspace):
        """SQLiteManager.for_workspace() should initialize workspace_meta for new DB."""
        temp_workspace.ensure_directories()

        # Create the database via factory
        db = SQLiteManager.for_workspace(temp_workspace)

        # Verify workspace_meta exists
        assert db.get_workspace_id() == temp_workspace.workspace_id
        db.close()

    def test_sqlite_mismatch_raises_workspace_mismatch_error(
        self, temp_workspace, another_workspace
    ):
        """Opening DB with wrong workspace_id should raise WorkspaceMismatchError."""
        temp_workspace.ensure_directories()
        another_workspace.ensure_directories()

        # Initialize first workspace DB
        db1 = SQLiteManager.for_workspace(temp_workspace)
        db1.close()

        # Try to open the same DB with different workspace_id
        with pytest.raises(WorkspaceMismatchError) as exc_info:
            SQLiteManager(
                db_path=temp_workspace.db_path,
                workspace_id=another_workspace.workspace_id,
            )

        assert temp_workspace.workspace_id in str(exc_info.value)
        assert another_workspace.workspace_id in str(exc_info.value)

    def test_sqlite_init_with_explicit_db_path_and_workspace_id(self, temp_workspace):
        """SQLiteManager with explicit db_path and workspace_id should work."""
        temp_workspace.ensure_directories()
        db = SQLiteManager(
            db_path=temp_workspace.db_path,
            workspace_id=temp_workspace.workspace_id,
        )
        assert db.db_path == temp_workspace.db_path
        assert db.get_workspace_id() == temp_workspace.workspace_id
        db.close()


class TestCRMStorageEnforcement:
    """Test CRMStorage workspace enforcement."""

    def test_crm_storage_requires_db_path(self):
        """CRMStorage() without db_path should raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            CRMStorage(None)
        assert "requires explicit db_path" in str(exc_info.value)

    def test_crm_storage_for_workspace_factory_creates_instance(self, temp_workspace):
        """CRMStorage.for_workspace() should create a workspace-bound instance."""
        temp_workspace.ensure_directories()
        storage = CRMStorage.for_workspace(temp_workspace)
        assert storage is not None
        assert storage.db_path == temp_workspace.db_path
        storage.close()


def _is_sqlite_manager_call(node: ast.Call) -> bool:
    """Check if an AST Call node is a call to SQLiteManager."""
    if isinstance(node.func, ast.Name):
        return node.func.id == "SQLiteManager"
    if isinstance(node.func, ast.Attribute):
        # Skip factory method calls like SQLiteManager.for_workspace()
        if node.func.attr == "for_workspace":
            return False
        return node.func.attr == "SQLiteManager"
    return False


def _has_valid_args(node: ast.Call) -> bool:
    """Check if a SQLiteManager call has valid (non-None) arguments."""
    # Has positional args that aren't None
    for arg in node.args:
        if not (isinstance(arg, ast.Constant) and arg.value is None):
            return True

    # Has keyword args with non-None values
    for kw in node.keywords:
        if kw.arg in ("db_path", "workspace_id"):
            if not (isinstance(kw.value, ast.Constant) and kw.value is None):
                return True

    return False


def _find_violations_in_file(py_file: Path, src_dir: Path) -> list:
    """Scan a Python file for parameterless SQLiteManager() calls."""
    violations = []
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_sqlite_manager_call(node):
            continue
        if _has_valid_args(node):
            continue
        if node.args or node.keywords:
            continue

        # This is SQLiteManager() with no args - violation!
        rel_path = py_file.relative_to(src_dir.parent.parent)
        violations.append(f"{rel_path}:{node.lineno} - SQLiteManager() called with no arguments")

    return violations


class TestNoGlobalFallbacks:
    """Test that no global fallbacks exist in production code."""

    def test_no_parameterless_sqlite_manager_calls_in_src(self):
        """Ensure no SQLiteManager() calls with empty args exist in src/.

        This test scans the AST of all Python files under src/agnetwork/
        and fails if any SQLiteManager() call is found without arguments.
        """
        src_dir = Path(__file__).parent.parent / "src" / "agnetwork"
        assert src_dir.exists(), f"Source directory not found: {src_dir}"

        violations = []
        for py_file in src_dir.rglob("*.py"):
            violations.extend(_find_violations_in_file(py_file, src_dir))

        if violations:
            pytest.fail(
                f"Found {len(violations)} SQLiteManager() calls without explicit db_path:\n"
                + "\n".join(violations)
            )

    def test_no_config_db_path_in_storage_modules(self):
        """Ensure storage modules don't use config.db_path fallback."""
        storage_files = [
            Path(__file__).parent.parent / "src" / "agnetwork" / "storage" / "sqlite.py",
            Path(__file__).parent.parent / "src" / "agnetwork" / "storage" / "memory.py",
            Path(__file__).parent.parent / "src" / "agnetwork" / "crm" / "storage.py",
        ]

        violations = []
        for storage_file in storage_files:
            if not storage_file.exists():
                continue

            content = storage_file.read_text(encoding="utf-8")

            # Check for patterns like "db_path or config.db_path" or "= config.db_path"
            if "or config.db_path" in content or "= config.db_path" in content:
                violations.append(str(storage_file))

        if violations:
            pytest.fail(
                "Found config.db_path fallback in storage modules:\n"
                + "\n".join(violations)
            )
