"""PR1: Storage enforcement tests.

Tests that verify workspace isolation is enforced at the storage layer:
- SQLiteManager requires explicit db_path AND workspace_id
- SQLiteManager.for_workspace() factory works correctly
- SQLiteManager.unscoped() provides explicit escape hatch for tests
- CRMStorage requires explicit db_path
- No unscoped SQLiteManager calls exist in src/ (enforced by AST)
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

    def test_sqlite_init_requires_db_path_and_workspace_id(self):
        """SQLiteManager() without db_path or workspace_id should raise TypeError."""
        # No args at all - TypeError
        with pytest.raises(TypeError):
            SQLiteManager()

        # db_path only - TypeError (workspace_id required)
        with pytest.raises(TypeError):
            SQLiteManager(db_path=Path("/tmp/test.db"))

    def test_sqlite_unscoped_escape_hatch(self, tmp_path):
        """SQLiteManager.unscoped() should work without workspace_id."""
        db_path = tmp_path / "test_unscoped.db"
        db = SQLiteManager.unscoped(db_path)
        assert db is not None
        assert db.db_path == db_path
        # Workspace ID should NOT be verified
        assert db._workspace_id is None
        db.close()

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
            CRMStorage(db_path=None, workspace_id="test")  # type: ignore
        assert "requires explicit db_path" in str(exc_info.value)

    def test_crm_storage_requires_workspace_id(self, tmp_path):
        """CRMStorage() without workspace_id should raise TypeError."""
        db_path = tmp_path / "crm.db"
        with pytest.raises(TypeError) as exc_info:
            CRMStorage(db_path=db_path)  # type: ignore  # Missing workspace_id
        assert "workspace_id" in str(exc_info.value) or "required" in str(exc_info.value)

    def test_crm_storage_for_workspace_factory_creates_instance(self, temp_workspace):
        """CRMStorage.for_workspace() should create a workspace-bound instance."""
        temp_workspace.ensure_directories()
        storage = CRMStorage.for_workspace(temp_workspace)
        assert storage is not None
        # PR3: CRM storage uses exports_dir/crm.db, not db_path
        assert storage.db_path == temp_workspace.exports_dir / "crm.db"
        assert storage.get_workspace_id() == temp_workspace.workspace_id
        storage.close()


def _is_sqlite_manager_call(node: ast.Call) -> bool:
    """Check if an AST Call node is a call to SQLiteManager."""
    if isinstance(node.func, ast.Name):
        return node.func.id == "SQLiteManager"
    if isinstance(node.func, ast.Attribute):
        # Skip factory/escape-hatch method calls
        if node.func.attr in ("for_workspace", "unscoped"):
            return False
        return node.func.attr == "SQLiteManager"
    return False


def _is_unscoped_call(node: ast.Call) -> bool:
    """Check if an AST Call node is SQLiteManager.unscoped()."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "unscoped"
    return False


def _has_workspace_id_kwarg(node: ast.Call) -> bool:
    """Check if a SQLiteManager call has workspace_id keyword argument."""
    for kw in node.keywords:
        if kw.arg == "workspace_id":
            return True
    return False


def _has_db_path_kwarg(node: ast.Call) -> bool:
    """Check if a SQLiteManager call has db_path keyword argument."""
    for kw in node.keywords:
        if kw.arg == "db_path":
            return True
    # Also check positional args
    return len(node.args) > 0


def _find_parameterless_violations(py_file: Path, src_dir: Path) -> list:
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

        # If no args at all - violation
        if not node.args and not node.keywords:
            rel_path = py_file.relative_to(src_dir.parent.parent)
            violations.append(
                f"{rel_path}:{node.lineno} - SQLiteManager() called with no arguments"
            )

    return violations


def _find_missing_workspace_id_violations(py_file: Path, src_dir: Path) -> list:
    """Scan for SQLiteManager(db_path=...) calls missing workspace_id in src/.

    Allowlist:
    - SQLiteManager.unscoped() calls (explicit bypass)
    - SQLiteManager.for_workspace() calls (handled separately)
    """
    violations = []
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Skip unscoped() calls - they are the explicit escape hatch
        if _is_unscoped_call(node):
            continue

        # Skip for_workspace() calls - they handle workspace_id internally
        if isinstance(node.func, ast.Attribute) and node.func.attr == "for_workspace":
            continue

        # Check for direct SQLiteManager() calls
        if not _is_sqlite_manager_call(node):
            continue

        # If has db_path but no workspace_id - violation
        if _has_db_path_kwarg(node) and not _has_workspace_id_kwarg(node):
            rel_path = py_file.relative_to(src_dir.parent.parent)
            violations.append(
                f"{rel_path}:{node.lineno} - SQLiteManager(db_path=...) missing workspace_id"
            )

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
            violations.extend(_find_parameterless_violations(py_file, src_dir))

        if violations:
            pytest.fail(
                f"Found {len(violations)} SQLiteManager() calls without arguments:\n"
                + "\n".join(violations)
            )

    def test_no_sqlite_manager_without_workspace_id_in_src(self):
        """Ensure no SQLiteManager(db_path=...) calls bypass workspace_id in src/.

        This test scans the AST of all Python files under src/agnetwork/
        and fails if any SQLiteManager(db_path=...) call is found without
        workspace_id parameter.

        Allowed patterns:
        - SQLiteManager.for_workspace(ws_ctx) - factory handles workspace_id
        - SQLiteManager.unscoped(db_path) - explicit escape hatch for tests/migrations
        - SQLiteManager(db_path=..., workspace_id=...) - fully specified
        """
        src_dir = Path(__file__).parent.parent / "src" / "agnetwork"
        assert src_dir.exists(), f"Source directory not found: {src_dir}"

        violations = []
        for py_file in src_dir.rglob("*.py"):
            violations.extend(_find_missing_workspace_id_violations(py_file, src_dir))

        if violations:
            pytest.fail(
                f"Found {len(violations)} SQLiteManager calls missing workspace_id:\n"
                + "\n".join(violations)
                + "\n\nUse SQLiteManager.for_workspace(ws_ctx) or "
                "SQLiteManager.unscoped(db_path) for tests/migrations."
            )

    def test_no_unscoped_calls_in_src(self):
        """Ensure SQLiteManager.unscoped() is never called in production code.

        unscoped() is an explicit escape hatch that bypasses workspace verification.
        It is ONLY allowed in:
        - tests/ directory
        - Explicitly named migrations modules (if they exist)

        Production code (src/agnetwork/**) must ALWAYS use:
        - SQLiteManager.for_workspace(ws_ctx)
        - SQLiteManager(db_path=..., workspace_id=...)
        """
        src_dir = Path(__file__).parent.parent / "src" / "agnetwork"
        assert src_dir.exists(), f"Source directory not found: {src_dir}"

        violations = []
        for py_file in src_dir.rglob("*.py"):
            # Allowlist: migrations module (if it exists)
            if "migrations" in py_file.parts:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _is_unscoped_call(node):
                    rel_path = py_file.relative_to(src_dir.parent.parent)
                    violations.append(
                        f"{rel_path}:{node.lineno} - SQLiteManager.unscoped() "
                        "called in production code"
                    )

        if violations:
            pytest.fail(
                f"Found {len(violations)} SQLiteManager.unscoped() calls in src/:\n"
                + "\n".join(violations)
                + "\n\nProduction code must use SQLiteManager.for_workspace(ws_ctx) "
                "or SQLiteManager(db_path=..., workspace_id=...)."
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
                "Found config.db_path fallback in storage modules:\n" + "\n".join(violations)
            )
