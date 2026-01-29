"""Tests for PR3: CRM Workspace Isolation.

Verifies that:
- CRMStorage requires workspace_id and enforces workspace guard (ID #2)
- CLI CRM commands only operate on active workspace (ID #8)
- No parameterless CRMStorage() calls in production code (anti-regression)
- No CRMStorage.unscoped() calls in production code (PR3.1)

These tests ensure CRM data doesn't leak across workspaces.
"""

import ast
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import pytest
from typer.testing import CliRunner

from agnetwork.cli import app
from agnetwork.crm.models import Account
from agnetwork.crm.storage import CRMStorage
from agnetwork.workspaces import WorkspaceMismatchError


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def two_workspaces() -> Generator[tuple, None, None]:
    """Create two isolated workspaces for testing.

    Yields:
        Tuple of (ws1_context, ws2_context, registry)
    """
    from agnetwork.workspaces.registry import WorkspaceRegistry

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_registry_root = Path(tmpdir)
        registry = WorkspaceRegistry(registry_root=temp_registry_root)

        # Create two workspaces
        ws1 = registry.create_workspace("workspace_one")
        ws2 = registry.create_workspace("workspace_two")

        # Patch WorkspaceRegistry to use our temp directory
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        try:
            yield ws1, ws2, registry
        finally:
            WorkspaceRegistry.__init__ = original_init


class TestCRMStorageWorkspaceEnforcement:
    """Tests for CRMStorage workspace isolation (Backlog ID #2)."""

    def test_crm_storage_requires_workspace_id(self):
        """CRMStorage constructor requires workspace_id parameter."""
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "crm.db"

            # Should fail without workspace_id
            with pytest.raises(TypeError) as exc_info:
                CRMStorage(db_path=db_path)  # type: ignore  # Missing workspace_id

            assert (
                "workspace_id" in str(exc_info.value).lower()
                or "required" in str(exc_info.value).lower()
            )

    def test_crm_storage_for_workspace_factory(self, two_workspaces):
        """CRMStorage.for_workspace() creates workspace-bound storage."""
        ws1, ws2, _ = two_workspaces

        # Create storage via factory
        storage1 = CRMStorage.for_workspace(ws1)

        # Should be bound to ws1's exports_dir
        assert storage1.db_path == ws1.exports_dir / "crm.db"

        # Verify workspace_id was stored
        assert storage1.get_workspace_id() == ws1.workspace_id

        storage1.close()

    def test_crm_storage_isolation_by_workspace_db(self, two_workspaces):
        """CRM data is isolated between workspaces."""
        ws1, ws2, _ = two_workspaces

        # Create test account
        test_account = Account(
            account_id="acc_test_isolation",
            name="Test Company Isolation",
            domain="testiso.com",
            created_at=datetime.now(timezone.utc),
        )

        # Insert into ws1
        storage1 = CRMStorage.for_workspace(ws1)
        storage1.insert_account(test_account)

        # Query ws2 - should NOT see ws1 data
        storage2 = CRMStorage.for_workspace(ws2)
        ws2_account = storage2.get_account("acc_test_isolation")

        assert ws2_account is None, "ws2 should NOT see ws1's account!"

        # Query ws1 - should see its data
        ws1_account = storage1.get_account("acc_test_isolation")
        assert ws1_account is not None
        assert ws1_account.name == "Test Company Isolation"

        storage1.close()
        storage2.close()

    def test_crm_storage_mismatch_raises_error(self, two_workspaces):
        """Opening ws1 CRM DB with ws2 workspace_id raises WorkspaceMismatchError."""
        ws1, ws2, _ = two_workspaces

        # Initialize ws1's CRM DB
        storage1 = CRMStorage.for_workspace(ws1)
        storage1.close()

        # Try to open ws1's DB with ws2's workspace_id
        with pytest.raises(WorkspaceMismatchError) as exc_info:
            CRMStorage(db_path=ws1.exports_dir / "crm.db", workspace_id=ws2.workspace_id)

        assert ws1.workspace_id in str(exc_info.value)
        assert ws2.workspace_id in str(exc_info.value)

    def test_crm_storage_unscoped_for_tests(self):
        """CRMStorage.unscoped() allows test access without workspace verification."""
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "crm.db"

            # Unscoped should work without workspace_id
            storage = CRMStorage.unscoped(db_path=db_path)

            # Should be usable
            stats = storage.get_stats()
            assert stats["accounts"] == 0

            storage.close()


class TestCRMCliWorkspaceIsolation:
    """Tests for CRM CLI commands workspace isolation (Backlog ID #8)."""

    def test_crm_list_respects_workspace(self, runner: CliRunner, two_workspaces):
        """crm list shows only accounts from active workspace."""
        ws1, ws2, registry = two_workspaces

        # Create account in ws1
        storage1 = CRMStorage.for_workspace(ws1)
        account1 = Account(
            account_id="acc_ws1_only",
            name="WS1 Company",
            domain="ws1only.com",
            created_at=datetime.now(timezone.utc),
        )
        storage1.insert_account(account1)
        storage1.close()

        # Create different account in ws2
        storage2 = CRMStorage.for_workspace(ws2)
        account2 = Account(
            account_id="acc_ws2_only",
            name="WS2 Company",
            domain="ws2only.com",
            created_at=datetime.now(timezone.utc),
        )
        storage2.insert_account(account2)
        storage2.close()

        # Set ws1 as default, list accounts
        registry.set_default_workspace("workspace_one")
        result1 = runner.invoke(app, ["crm", "list", "accounts"])

        assert result1.exit_code == 0, f"Failed: {result1.output}"
        assert "WS1 Company" in result1.output
        assert "WS2 Company" not in result1.output
        assert "workspace_one" in result1.output.lower()

        # Set ws2 as default, list accounts
        registry.set_default_workspace("workspace_two")
        result2 = runner.invoke(app, ["crm", "list", "accounts"])

        assert result2.exit_code == 0, f"Failed: {result2.output}"
        assert "WS2 Company" in result2.output
        assert "WS1 Company" not in result2.output
        assert "workspace_two" in result2.output.lower()

    def test_crm_stats_respects_workspace(self, runner: CliRunner, two_workspaces):
        """crm stats shows only counts from active workspace."""
        ws1, ws2, registry = two_workspaces

        # Insert 2 accounts in ws1
        storage1 = CRMStorage.for_workspace(ws1)
        for i in range(2):
            storage1.insert_account(
                Account(
                    account_id=f"acc_ws1_{i}",
                    name=f"WS1 Company {i}",
                    created_at=datetime.now(timezone.utc),
                )
            )
        storage1.close()

        # Insert 5 accounts in ws2
        storage2 = CRMStorage.for_workspace(ws2)
        for i in range(5):
            storage2.insert_account(
                Account(
                    account_id=f"acc_ws2_{i}",
                    name=f"WS2 Company {i}",
                    created_at=datetime.now(timezone.utc),
                )
            )
        storage2.close()

        # Set ws1 as default
        registry.set_default_workspace("workspace_one")
        result1 = runner.invoke(app, ["crm", "stats"])

        assert result1.exit_code == 0, f"Failed: {result1.output}"
        assert "Accounts:   2" in result1.output

        # Set ws2 as default
        registry.set_default_workspace("workspace_two")
        result2 = runner.invoke(app, ["crm", "stats"])

        assert result2.exit_code == 0, f"Failed: {result2.output}"
        assert "Accounts:   5" in result2.output

    def test_crm_search_respects_workspace(self, runner: CliRunner, two_workspaces):
        """crm search shows only results from active workspace."""
        ws1, ws2, registry = two_workspaces

        # Insert searchable account in ws1
        storage1 = CRMStorage.for_workspace(ws1)
        storage1.insert_account(
            Account(
                account_id="acc_searchable_ws1",
                name="TechStartup Alpha",
                domain="techstartup.com",
                created_at=datetime.now(timezone.utc),
            )
        )
        storage1.close()

        # Insert same-keyword account in ws2
        storage2 = CRMStorage.for_workspace(ws2)
        storage2.insert_account(
            Account(
                account_id="acc_searchable_ws2",
                name="TechStartup Beta",
                domain="techbeta.com",
                created_at=datetime.now(timezone.utc),
            )
        )
        storage2.close()

        # Search in ws1
        registry.set_default_workspace("workspace_one")
        result1 = runner.invoke(app, ["crm", "search", "TechStartup"])

        assert result1.exit_code == 0, f"Failed: {result1.output}"
        assert "Alpha" in result1.output
        assert "Beta" not in result1.output

        # Search in ws2
        registry.set_default_workspace("workspace_two")
        result2 = runner.invoke(app, ["crm", "search", "TechStartup"])

        assert result2.exit_code == 0, f"Failed: {result2.output}"
        assert "Beta" in result2.output
        assert "Alpha" not in result2.output


class TestNoCRMStorageGlobalFallbacks:
    """Anti-regression tests to ensure CRMStorage cannot be called without workspace scope."""

    def test_no_parameterless_crm_storage_in_src(self):
        """Ensure no CRMStorage() calls without workspace_id in production code.

        Scans src/agnetwork/**/*.py and fails if any CRMStorage instantiation
        is found without workspace_id argument.
        """
        src_root = Path(__file__).parent.parent / "src" / "agnetwork"
        violations = []

        for py_file in src_root.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for CRMStorage(...) calls
                    func = node.func
                    is_crm_storage_call = False

                    if isinstance(func, ast.Name) and func.id == "CRMStorage":
                        is_crm_storage_call = True
                    elif isinstance(func, ast.Attribute) and func.attr == "CRMStorage":
                        is_crm_storage_call = True

                    if is_crm_storage_call:
                        # Check if workspace_id is provided
                        has_workspace_id = any(kw.arg == "workspace_id" for kw in node.keywords)
                        # Also check for factory methods which don't need workspace_id
                        # (for_workspace, unscoped are fine)
                        if isinstance(func, ast.Attribute) and func.attr in (
                            "for_workspace",
                            "unscoped",
                        ):
                            continue

                        if not has_workspace_id:
                            violations.append(
                                f"{py_file.relative_to(src_root.parent.parent)}:{node.lineno}"
                            )

        assert not violations, "Found CRMStorage calls without workspace_id:\n" + "\n".join(
            violations
        )

    def test_no_crmstorage_unscoped_in_src(self):
        """Ensure CRMStorage.unscoped() is never called in production code.

        unscoped() is an explicit escape hatch that bypasses workspace verification.
        It is ONLY allowed in:
        - tests/ directory
        - Explicitly allowlisted migration modules (if they exist)

        Production code (src/agnetwork/**) must ALWAYS use:
        - CRMStorage.for_workspace(ws_ctx)
        - CRMStorage(db_path=..., workspace_id=...)
        """
        # Allowlist for legitimate migration modules (currently empty)
        ALLOWLIST: set[str] = set()

        src_root = Path(__file__).parent.parent / "src" / "agnetwork"
        assert src_root.exists(), f"Source directory not found: {src_root}"

        violations = []
        for py_file in src_root.rglob("*.py"):
            rel_path = str(py_file.relative_to(src_root.parent.parent))

            # Skip allowlisted paths
            if rel_path.replace("\\", "/") in ALLOWLIST:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                # Check for CRMStorage.unscoped(...) pattern
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "unscoped":
                    # Verify it's CRMStorage.unscoped, not some other class
                    if isinstance(func.value, ast.Name) and func.value.id == "CRMStorage":
                        violations.append(
                            f"{rel_path}:{node.lineno} - CRMStorage.unscoped() "
                            "called in production code"
                        )

        assert not violations, (
            f"Found {len(violations)} CRMStorage.unscoped() calls in src/:\n"
            + "\n".join(violations)
            + "\n\nProduction code must use CRMStorage.for_workspace(ws_ctx) "
            "or CRMStorage(db_path=..., workspace_id=...)."
        )

    def test_no_crm_adapter_from_env_in_cli(self):
        """Ensure CLI doesn't use CRMAdapterFactory.from_env() (dev-only method)."""
        cli_path = Path(__file__).parent.parent / "src" / "agnetwork" / "cli.py"
        source = cli_path.read_text(encoding="utf-8")

        # Search for from_env usage in CRM command section
        in_crm_section = False
        violations = []

        for i, line in enumerate(source.split("\n"), 1):
            if "crm_app" in line or "@crm_app" in line:
                in_crm_section = True
            if in_crm_section and "from_env()" in line:
                violations.append(f"cli.py:{i}: {line.strip()}")
            # Exit CRM section when we hit sequence_app
            if "sequence_app" in line:
                in_crm_section = False

        assert not violations, (
            "Found CRMAdapterFactory.from_env() in CLI CRM commands:\n" + "\n".join(violations)
        )

    def test_no_global_crm_exports_path_in_cli(self):
        """Ensure CLI doesn't use config.project_root / 'data' / 'crm_exports'."""
        cli_path = Path(__file__).parent.parent / "src" / "agnetwork" / "cli.py"
        source = cli_path.read_text(encoding="utf-8")

        violations = []
        for i, line in enumerate(source.split("\n"), 1):
            if "crm_exports" in line and "config" in line:
                violations.append(f"cli.py:{i}: {line.strip()}")

        assert not violations, "Found global crm_exports path in CLI:\n" + "\n".join(violations)


class TestCRMAdapterFactoryWorkspaceEnforcement:
    """Tests for CRMAdapterFactory workspace enforcement."""

    def test_factory_create_requires_workspace_context(self):
        """CRMAdapterFactory.create('file') requires ws_ctx or workspace_id."""
        from agnetwork.crm.adapters import CRMAdapterFactory

        with pytest.raises(TypeError) as exc_info:
            CRMAdapterFactory.create("file")

        assert "workspace" in str(exc_info.value).lower()

    def test_factory_create_with_ws_ctx(self, two_workspaces):
        """CRMAdapterFactory.create('file', ws_ctx=...) works correctly."""
        from agnetwork.crm.adapters import CRMAdapterFactory

        ws1, _, _ = two_workspaces

        adapter = CRMAdapterFactory.create("file", ws_ctx=ws1)

        # Should be usable
        accounts = adapter.list_accounts()
        assert accounts == []

    def test_factory_from_env_requires_both_env_vars(self, monkeypatch):
        """from_env() requires both AG_CRM_PATH and AG_CRM_WORKSPACE_ID."""
        from agnetwork.crm.adapters import CRMAdapterFactory

        # Clear both env vars
        monkeypatch.delenv("AG_CRM_PATH", raising=False)
        monkeypatch.delenv("AG_CRM_WORKSPACE_ID", raising=False)

        with pytest.raises(TypeError) as exc_info:
            CRMAdapterFactory.from_env()

        error_msg = str(exc_info.value).lower()
        assert "ag_crm_path" in error_msg or "ag_crm_workspace_id" in error_msg

    def test_factory_from_env_with_only_path_fails(self, monkeypatch, tmp_path):
        """from_env() with only AG_CRM_PATH (no workspace_id) fails."""
        from agnetwork.crm.adapters import CRMAdapterFactory

        monkeypatch.setenv("AG_CRM_PATH", str(tmp_path))
        monkeypatch.delenv("AG_CRM_WORKSPACE_ID", raising=False)

        with pytest.raises(TypeError) as exc_info:
            CRMAdapterFactory.from_env()

        assert "AG_CRM_WORKSPACE_ID" in str(exc_info.value)
