"""Performance baseline tests for ag_network.

These tests establish repeatable performance baselines that can be run
offline without network access or LLM providers.

Run with: pytest tests/test_perf_baseline.py -v
"""

from __future__ import annotations

import gc
import json
import os
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from typer.testing import CliRunner

# =============================================================================
# Configuration
# =============================================================================

# Number of iterations for each benchmark (median is reported)
ITERATIONS = 3

# Synthetic data sizes
STORAGE_INSERT_COUNT = 100
STORAGE_QUERY_COUNT = 10

# Performance targets (ms) - generous initial targets for baseline
TARGETS = {
    "cli_startup_warm_ms": 1500,  # CLI startup can be slow with many imports
    "storage_insert_100_ms": 1000,  # Includes DB creation + schema init each run
    "storage_fts_query_avg_ms": 50,  # FTS queries with small dataset
    "pipeline_manual_ms": 5000,  # Full pipeline in manual mode
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""

    name: str
    median_ms: float
    min_ms: float
    max_ms: float
    target_ms: float
    passed: bool
    iterations: int = ITERATIONS
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerfReport:
    """Complete performance report."""

    version: str
    timestamp: str
    machine: dict[str, Any]
    benchmarks: dict[str, BenchmarkResult]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "machine": self.machine,
            "benchmarks": {
                name: {
                    "median_ms": round(r.median_ms, 2),
                    "min_ms": round(r.min_ms, 2),
                    "max_ms": round(r.max_ms, 2),
                    "target_ms": r.target_ms,
                    "passed": r.passed,
                    "iterations": r.iterations,
                    **r.details,
                }
                for name, r in self.benchmarks.items()
            },
            "notes": self.notes,
        }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def perf_report() -> PerfReport:
    """Create a performance report that accumulates results."""
    from agnetwork import __version__

    return PerfReport(
        version=__version__,
        timestamp=datetime.now(timezone.utc).isoformat(),
        machine={
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        benchmarks={},
    )


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def isolated_workspace():
    """Create an isolated workspace for benchmarks."""
    from agnetwork.workspaces.registry import WorkspaceRegistry

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_registry_root = Path(tmpdir)
        registry = WorkspaceRegistry(registry_root=temp_registry_root)
        workspace = registry.create_workspace("perf_test")
        registry.set_default_workspace("perf_test")

        # Patch for isolation
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        try:
            yield workspace
        finally:
            WorkspaceRegistry.__init__ = original_init
            gc.collect()


# =============================================================================
# Helpers
# =============================================================================


def measure_ms(func, iterations: int = ITERATIONS) -> tuple[float, float, float]:
    """Measure function execution time in milliseconds.

    Returns:
        Tuple of (median, min, max) in milliseconds.
    """
    times = []
    for _ in range(iterations):
        gc.collect()  # Reduce GC noise
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    times.sort()
    median_idx = len(times) // 2
    return times[median_idx], times[0], times[-1]


def create_benchmark_result(
    name: str,
    times: tuple[float, float, float],
    target_key: str,
    **details: Any,
) -> BenchmarkResult:
    """Create a BenchmarkResult from timing data."""
    median, min_t, max_t = times
    target = TARGETS[target_key]
    return BenchmarkResult(
        name=name,
        median_ms=median,
        min_ms=min_t,
        max_ms=max_t,
        target_ms=target,
        passed=median <= target,
        details=details,
    )


# =============================================================================
# Benchmarks
# =============================================================================


class TestPerfBaseline:
    """Performance baseline tests."""

    @pytest.mark.perf
    def test_cli_startup_warm(self, perf_report: PerfReport, runner: CliRunner):
        """Benchmark CLI startup time (warm)."""
        from agnetwork.cli import app

        # Warm-up run (not measured)
        runner.invoke(app, ["--help"])

        def run_cli_help():
            runner.invoke(app, ["--help"])

        times = measure_ms(run_cli_help)
        result = create_benchmark_result(
            "cli_startup_warm",
            times,
            "cli_startup_warm_ms",
        )
        perf_report.benchmarks["cli_startup_warm"] = result

        assert result.passed, (
            f"CLI startup ({result.median_ms:.1f}ms) exceeds target ({result.target_ms}ms)"
        )

    @pytest.mark.perf
    def test_storage_insert_batch(self, perf_report: PerfReport, isolated_workspace):
        """Benchmark storage insert operations."""
        from agnetwork.storage.sqlite import SQLiteManager

        def run_inserts():
            # Create fresh storage each time (includes schema init)
            db_path = isolated_workspace.root_dir / f"perf_test_{time.time_ns()}.db"
            storage = SQLiteManager(db_path, workspace_id=isolated_workspace.workspace_id)

            # Insert synthetic source records
            for i in range(STORAGE_INSERT_COUNT):
                storage.insert_source(
                    source_id=f"src_{i}",
                    source_type="web",
                    content=f"Content for page {i}. " * 50,  # ~300 chars
                    title=f"Test Page {i} - Lorem ipsum dolor sit amet",
                    uri=f"https://example.com/page/{i}",
                )

            storage.close()

        times = measure_ms(run_inserts)
        per_record = times[0] / STORAGE_INSERT_COUNT

        result = create_benchmark_result(
            "storage_insert_100",
            times,
            "storage_insert_100_ms",
            per_record_ms=round(per_record, 3),
            record_count=STORAGE_INSERT_COUNT,
        )
        perf_report.benchmarks["storage_insert_100"] = result

        assert result.passed, (
            f"Storage insert ({result.median_ms:.1f}ms) exceeds target ({result.target_ms}ms)"
        )

    @pytest.mark.perf
    def test_storage_fts_search(self, perf_report: PerfReport, isolated_workspace):
        """Benchmark FTS search operations."""
        from agnetwork.storage.sqlite import SQLiteManager

        # Setup: Create storage with data
        db_path = isolated_workspace.root_dir / "fts_test.db"
        storage = SQLiteManager(db_path, workspace_id=isolated_workspace.workspace_id)

        # Insert test data
        for i in range(STORAGE_INSERT_COUNT):
            storage.insert_source(
                source_id=f"src_{i}",
                source_type="web",
                content=f"Content for page {i}. Unique term{i} appears here. " * 20,
                title=f"Test Page {i} - Lorem ipsum dolor sit amet",
                uri=f"https://example.com/page/{i}",
            )

        # Queries to test
        queries = [
            "lorem ipsum",
            "test page",
            "unique term50",
            "content page",
            "example",
            "dolor sit amet",
            "term25",
            "page 10",
            "fetched",
            "company",
        ]

        def run_queries():
            for q in queries[:STORAGE_QUERY_COUNT]:
                storage.search_sources_fts(q, limit=10)

        times = measure_ms(run_queries)
        per_query = times[0] / STORAGE_QUERY_COUNT

        result = create_benchmark_result(
            "storage_fts_query",
            times,
            "storage_fts_query_avg_ms",
            per_query_ms=round(per_query, 3),
            query_count=STORAGE_QUERY_COUNT,
        )
        perf_report.benchmarks["storage_fts_query"] = result

        storage.close()

        assert result.passed, (
            f"FTS query avg ({per_query:.1f}ms) exceeds target ({result.target_ms}ms)"
        )

    @pytest.mark.perf
    def test_pipeline_manual_mode(
        self, perf_report: PerfReport, runner: CliRunner, isolated_workspace
    ):
        """Benchmark pipeline execution in manual mode (no LLM)."""
        from agnetwork.cli import app
        from agnetwork.workspaces.registry import WorkspaceRegistry

        # Ensure isolated workspace is used
        temp_registry_root = isolated_workspace.root_dir.parent
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        def run_pipeline():
            result = runner.invoke(
                app,
                [
                    "run-pipeline",
                    "BenchmarkCorp",
                    "--snapshot",
                    "A test company for performance benchmarking",
                    "--pain",
                    "Performance issues",
                    "--persona",
                    "CTO",
                    "--mode",
                    "manual",
                ],
            )
            assert result.exit_code == 0, f"Pipeline failed: {result.output}"

        try:
            times = measure_ms(run_pipeline)
        finally:
            WorkspaceRegistry.__init__ = original_init

        result = create_benchmark_result(
            "pipeline_manual",
            times,
            "pipeline_manual_ms",
        )
        perf_report.benchmarks["pipeline_manual"] = result

        assert result.passed, (
            f"Pipeline ({result.median_ms:.1f}ms) exceeds target ({result.target_ms}ms)"
        )


# =============================================================================
# Report Output
# =============================================================================


@pytest.fixture(scope="module", autouse=True)
def output_report(perf_report: PerfReport, request):
    """Output performance report after all tests complete."""
    yield

    # Only output if we have results
    if not perf_report.benchmarks:
        return

    # Print summary to console
    print("\n" + "=" * 60)
    print("PERFORMANCE BASELINE RESULTS")
    print("=" * 60)
    print(f"Version: {perf_report.version}")
    print(f"Platform: {perf_report.machine['platform']}")
    print(f"Python: {perf_report.machine['python']}")
    print("-" * 60)

    for name, result in perf_report.benchmarks.items():
        status = "✓" if result.passed else "✗"
        print(
            f"{status} {name}: {result.median_ms:.1f}ms "
            f"(target: {result.target_ms}ms) "
            f"[{result.min_ms:.1f}-{result.max_ms:.1f}ms]"
        )

    print("=" * 60)

    # Write JSON report if output path specified
    output_path = request.config.getoption("--perf-output", default=None)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(perf_report.to_dict(), f, indent=2)
        print(f"Report written to: {output_path}")


def pytest_addoption(parser):
    """Add pytest command line options."""
    parser.addoption(
        "--perf-output",
        action="store",
        default=None,
        help="Path to write JSON performance report",
    )
