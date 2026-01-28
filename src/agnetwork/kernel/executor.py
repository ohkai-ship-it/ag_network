"""Kernel executor for running execution plans.

The executor takes a Plan and executes it step by step,
calling skills and collecting results. It delegates persistence
to the RunManager/Orchestrator.

M4 additions:
- Memory retrieval integration (--use-memory flag)
- Claim persistence with evidence tracking
- EvidenceBundle passed to skill context
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type

from agnetwork.kernel.contracts import (
    ArtifactKind,
    SkillContext,
    SkillResult,
)
from agnetwork.kernel.models import ExecutionMode, Plan, Step, StepStatus, TaskSpec
from agnetwork.kernel.planner import Planner
from agnetwork.orchestrator import RunManager


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self):
        self._skills: Dict[str, Any] = {}
        self._skill_classes: Dict[str, Type] = {}

    def register(self, name: str, skill_class: Type) -> None:
        """Register a skill class by name."""
        self._skill_classes[name] = skill_class

    def get(self, name: str) -> Optional[Any]:
        """Get a skill instance by name."""
        if name in self._skills:
            return self._skills[name]

        if name in self._skill_classes:
            skill = self._skill_classes[name]()
            self._skills[name] = skill
            return skill

        return None

    def has(self, name: str) -> bool:
        """Check if a skill is registered."""
        return name in self._skill_classes


# Global skill registry
skill_registry = SkillRegistry()


def register_skill(name: str) -> Callable[[Type], Type]:
    """Decorator to register a skill class."""

    def decorator(cls: Type) -> Type:
        skill_registry.register(name, cls)
        return cls

    return decorator


class ExecutionResult:
    """Result of executing a plan."""

    def __init__(self):
        self.success: bool = True
        self.step_results: Dict[str, SkillResult] = {}
        self.errors: List[str] = []
        self.run_id: Optional[str] = None
        self.artifacts_written: List[str] = []
        self.verification_issues: List[Dict[str, Any]] = []
        self.mode: ExecutionMode = ExecutionMode.MANUAL
        self.memory_enabled: bool = False
        self.claims_persisted: int = 0


    def add_step_result(self, step_id: str, result: SkillResult) -> None:
        """Add a step result."""
        self.step_results[step_id] = result

    def add_error(self, error: str) -> None:
        """Add an error."""
        self.errors.append(error)
        self.success = False


class KernelExecutor:
    """Executes plans by running skills and managing persistence.

    The executor:
    1. Creates a RunManager for the execution
    2. Iterates through plan steps
    3. Calls skills with appropriate context
    4. Delegates artifact writing to RunManager
    5. Updates status and logs
    6. (M4) Persists claims with evidence links

    Supports two execution modes:
    - MANUAL: Deterministic template-based generation (default)
    - LLM: LLM-assisted generation with structured validation

    M4: Supports memory retrieval toggle (use_memory flag).
    """

    def __init__(
        self,
        verifier: Optional[Any] = None,
        mode: ExecutionMode = ExecutionMode.MANUAL,
        llm_factory: Optional[Any] = None,
        use_memory: bool = False,
    ):
        """Initialize the executor.

        Args:
            verifier: Optional verifier to validate skill results
            mode: Execution mode (MANUAL or LLM)
            llm_factory: LLM factory for LLM mode (required if mode=LLM)
            use_memory: Enable memory retrieval for context (M4)
        """
        self.planner = Planner()
        self.verifier = verifier
        self.mode = mode
        self.llm_factory = llm_factory
        self.use_memory = use_memory
        self._llm_executor: Optional[Any] = None
        self._memory_api: Optional[Any] = None

    def _get_llm_executor(self):
        """Get or create LLM skill executor (lazy initialization)."""
        if self._llm_executor is None:
            from agnetwork.kernel.llm_executor import LLMSkillExecutor
            self._llm_executor = LLMSkillExecutor(
                llm_factory=self.llm_factory,
                enable_critic=True,
                max_repairs=2,
            )
        return self._llm_executor

    def _get_memory_api(self, db_path=None):
        """Get or create Memory API (lazy initialization).
        
        Args:
            db_path: Optional path to workspace database. If provided and different
                     from cached, creates a new MemoryAPI instance.
        """
        # If db_path is provided and we have a cached API with different path, recreate
        if db_path is not None:
            from agnetwork.storage.memory import MemoryAPI
            return MemoryAPI(db_path=db_path)
        
        if self._memory_api is None:
            from agnetwork.storage.memory import MemoryAPI
            self._memory_api = MemoryAPI()
        return self._memory_api

    def execute_task(
        self,
        task_spec: TaskSpec,
        use_memory: Optional[bool] = None,
        run_manager: Optional[Any] = None,
    ) -> ExecutionResult:
        """Execute a task specification.

        Creates a plan and executes it.

        Args:
            task_spec: The task to execute
            use_memory: Override memory setting for this execution
            run_manager: Optional existing RunManager to reuse (for unified run folders)

        Returns:
            ExecutionResult with results and any errors
        """
        plan = self.planner.create_plan(task_spec)
        return self.execute_plan(plan, use_memory=use_memory, run_manager=run_manager)

    def execute_plan(
        self,
        plan: Plan,
        use_memory: Optional[bool] = None,
        run_manager: Optional[Any] = None,
    ) -> ExecutionResult:  # noqa: C901
        """Execute an execution plan.

        Args:
            plan: The plan to execute
            use_memory: Override memory setting for this execution
            run_manager: Optional existing RunManager to reuse (for unified run folders)

        Returns:
            ExecutionResult with results and any errors
        """
        # Determine if memory is enabled for this run
        memory_enabled = use_memory if use_memory is not None else self.use_memory

        result = ExecutionResult()
        result.mode = self.mode
        result.memory_enabled = memory_enabled

        # Use provided run manager or create new one
        task_spec = plan.task_spec
        workspace_ctx = getattr(task_spec, 'workspace_context', None)
        
        if run_manager is not None:
            run = run_manager
        else:
            # Create run manager with workspace context if provided
            command = (
                "pipeline"
                if task_spec.task_type.value == "pipeline"
                else task_spec.task_type.value
            )
            # M7.1: Pass workspace context to RunManager for scoped runs
            run = RunManager(command=command, slug=task_spec.get_slug(), workspace=workspace_ctx)
        result.run_id = run.run_id

        # Save inputs
        run.save_inputs(task_spec.inputs)

        # M4: Retrieve evidence bundle if memory is enabled
        evidence_bundle = None
        if memory_enabled:
            try:
                # M8: Use workspace-specific database if available
                db_path = workspace_ctx.db_path if workspace_ctx else None
                memory_api = self._get_memory_api(db_path=db_path)
                evidence_bundle = memory_api.retrieve_context(task_spec)
                run.log_action(
                    phase="memory",
                    action="Retrieved evidence context",
                    status="success",
                    changes_made=[
                        f"sources: {len(evidence_bundle.sources)}",
                        f"artifacts: {len(evidence_bundle.artifacts)}",
                    ],
                )
            except Exception as e:
                run.log_action(
                    phase="memory",
                    action="Memory retrieval failed",
                    status="warning",
                    issues_discovered=[str(e)],
                )

        # Log plan start with mode
        run.log_action(
            phase="plan",
            action=f"Starting plan {plan.plan_id} (mode={self.mode.value}, memory={memory_enabled})",
            status="success",
            next_action=f"Execute {len(plan.steps)} steps",
        )

        plan.mark_started()

        # Execute steps
        step_outputs: Dict[str, Any] = {}

        while not plan.is_complete() and not plan.has_failed():
            step = plan.get_next_step()
            if step is None:
                break

            step_result = self._execute_step(
                step, task_spec, run, step_outputs,
                evidence_bundle=evidence_bundle,
                memory_enabled=memory_enabled,
            )
            self._process_step_result(step, step_result, result, step_outputs, run)

        plan.mark_completed()
        self._finalize_plan(plan, result, run)

        return result

    def _process_step_result(
        self,
        step: Step,
        step_result: Optional[SkillResult],
        result: ExecutionResult,
        step_outputs: Dict[str, Any],
        run: RunManager,
    ) -> None:
        """Process the result of a step execution."""
        if not step_result:
            result.add_error(f"Step {step.step_id} returned no result")
            return

        result.add_step_result(step.step_id, step_result)

        # Store outputs for dependent steps
        if step_result.output:
            step_outputs[step.step_id] = step_result.output

        # Verify result if verifier is available
        if self.verifier:
            issues = self.verifier.verify_skill_result(
                step_result, memory_enabled=result.memory_enabled
            )
            if issues:
                # Convert Issue objects to dicts
                issue_dicts = [i.to_dict() for i in issues]
                result.verification_issues.extend(issue_dicts)
                for issue in issue_dicts:
                    if issue.get("severity") == "error":
                        step.mark_failed(f"Verification failed: {issue.get('message')}")
                        result.add_error(issue.get("message", "Unknown verification error"))
                        self._mark_run_failed(run, issue_dicts)
                        return

        # Persist artifacts via RunManager
        if step.status != StepStatus.FAILED:
            artifacts_info = self._persist_artifacts_via_runmanager(step_result, run)
            result.artifacts_written.extend(
                [a.filename for a in step_result.artifacts]
            )

            # M4: Persist claims with evidence links
            claims_count = self._persist_claims(step_result, artifacts_info, run)
            result.claims_persisted += claims_count

    def _persist_claims(
        self,
        result: SkillResult,
        artifacts_info: Dict[str, str],
        run: RunManager,
    ) -> int:
        """Persist claims from skill result to database.

        Args:
            result: SkillResult containing claims
            artifacts_info: Mapping of artifact_name -> artifact_id
            run: RunManager for this run

        Returns:
            Number of claims persisted
        """
        if not result.claims:
            return 0

        from agnetwork.storage.sqlite import SQLiteManager

        try:
            db = SQLiteManager()
            count = 0

            # Get first artifact ID (claims typically belong to the primary artifact)
            artifact_id = None
            if artifacts_info:
                artifact_id = next(iter(artifacts_info.values()), None)

            if not artifact_id:
                # Generate an artifact ID based on run_id and skill
                artifact_id = f"{run.run_id}_{result.skill_name}"

            for claim in result.claims:
                claim_id = f"claim_{run.run_id}_{uuid.uuid4().hex[:8]}"
                source_ids = claim.source_ids if claim.is_sourced() else []

                # M8 TODO: Once claims schema supports evidence JSON, persist
                # evidence snippets here. For now, evidence is stored in artifacts
                # and linked via source_ids.
                db.insert_claim(
                    claim_id=claim_id,
                    artifact_id=artifact_id,
                    claim_text=claim.text,
                    kind=claim.kind.value,
                    source_ids=source_ids,
                    confidence=claim.confidence,
                )
                count += 1

            return count
        except Exception as e:
            run.log_action(
                phase="claims",
                action="Claim persistence failed",
                status="warning",
                issues_discovered=[str(e)],
            )
            return 0

    def _finalize_plan(
        self, plan: Plan, result: ExecutionResult, run: RunManager
    ) -> None:
        """Finalize plan execution and update status."""
        if plan.has_failed():
            result.success = False
            run.update_status(
                current_phase="failed",
                phases_completed=[],
                phases_in_progress=[],
            )
            run.log_action(
                phase="complete",
                action="Plan execution failed",
                status="failure",
                issues_discovered=result.errors,
            )
        else:
            run.update_status(
                current_phase="complete",
                phases_completed=[s.step_id for s in plan.steps],
                phases_in_progress=[],
            )
            run.log_action(
                phase="complete",
                action=f"Plan execution completed (claims={result.claims_persisted})",
                status="success",
                changes_made=result.artifacts_written,
            )

    def _execute_step(
        self,
        step: Step,
        task_spec: TaskSpec,
        run: RunManager,
        step_outputs: Dict[str, Any],
        evidence_bundle: Optional[Any] = None,
        memory_enabled: bool = False,
    ) -> Optional[SkillResult]:
        """Execute a single step.

        Args:
            step: The step to execute
            task_spec: The task specification
            run: The run manager for logging
            step_outputs: Outputs from previous steps
            evidence_bundle: Retrieved evidence (M4)
            memory_enabled: Whether memory retrieval is enabled (M4)

        Returns:
            SkillResult if successful, None otherwise
        """
        step.mark_running()

        run.log_action(
            phase=step.step_id,
            action=f"Executing skill: {step.skill_name} (mode={self.mode.value})",
            status="in_progress",
        )

        # M8: Get actual workspace name from workspace_context if available
        workspace_ctx = getattr(task_spec, 'workspace_context', None)
        workspace_name = workspace_ctx.name if workspace_ctx else task_spec.workspace.value

        # Build context with evidence bundle if available
        context = SkillContext(
            run_id=run.run_id,
            workspace=workspace_name,
            step_inputs={
                dep_id: step_outputs.get(dep_id) for dep_id in step.depends_on
            },
            evidence_bundle=evidence_bundle,
            memory_enabled=memory_enabled,
        )

        try:
            # Execute based on mode
            if self.mode == ExecutionMode.LLM:
                result = self._execute_step_llm(step, task_spec, context)
            else:
                result = self._execute_step_manual(step, task_spec, context)

            if result is None:
                return None

            # Set skill metadata
            result.skill_name = step.skill_name
            if self.mode == ExecutionMode.LLM:
                result.skill_version = getattr(result, "skill_version", "1.0") + "-llm"

            step.mark_completed()

            run.log_action(
                phase=step.step_id,
                action=f"Skill {step.skill_name} completed",
                status="success",
                changes_made=[a.filename for a in result.artifacts],
            )

            return result

        except Exception as e:
            step.mark_failed(str(e))
            run.log_action(
                phase=step.step_id,
                action=f"Skill {step.skill_name} failed",
                status="failure",
                issues_discovered=[str(e)],
            )
            return None

    def _execute_step_manual(
        self,
        step: Step,
        task_spec: TaskSpec,
        context: SkillContext,
    ) -> Optional[SkillResult]:
        """Execute a step using manual (deterministic) mode.

        Args:
            step: The step to execute
            task_spec: Task specification
            context: Execution context

        Returns:
            SkillResult if successful, None otherwise
        """
        # Get skill from registry
        skill = skill_registry.get(step.skill_name)
        if skill is None:
            return None

        start_time = datetime.now(timezone.utc)
        result = skill.run(step.input_ref, context)
        end_time = datetime.now(timezone.utc)

        # Update metrics
        if result.metrics:
            result.metrics.execution_time_ms = (
                end_time - start_time
            ).total_seconds() * 1000

        if hasattr(skill, "version"):
            result.skill_version = skill.version

        return result

    def _execute_step_llm(
        self,
        step: Step,
        task_spec: TaskSpec,
        context: SkillContext,
    ) -> Optional[SkillResult]:
        """Execute a step using LLM mode.

        Args:
            step: The step to execute
            task_spec: Task specification
            context: Execution context

        Returns:
            SkillResult if successful, None otherwise
        """
        from agnetwork.kernel.llm_executor import SKILL_EXECUTORS, LLMSkillError

        llm_executor = self._get_llm_executor()

        # Check if skill is supported in LLM mode
        if step.skill_name not in SKILL_EXECUTORS:
            # Fall back to manual mode for unsupported skills
            return self._execute_step_manual(step, task_spec, context)

        # Get executor method
        method_name = SKILL_EXECUTORS[step.skill_name]
        executor_method = getattr(llm_executor, method_name)

        try:
            return executor_method(step.input_ref, context)
        except LLMSkillError as e:
            raise RuntimeError(f"LLM skill execution failed: {e}") from e

    def _persist_artifacts_via_runmanager(
        self, result: SkillResult, run: RunManager
    ) -> Dict[str, str]:
        """Persist artifacts via RunManager.

        The KernelExecutor does NOT write files directly. All artifact
        persistence is delegated to RunManager which handles:
        - File writing to run folder
        - Version metadata injection
        - Worklog updates

        Args:
            result: The skill result with artifacts
            run: The run manager that handles actual persistence

        Returns:
            Mapping of artifact_name -> artifact_id (for claim linking)
        """
        # Group artifacts by name (MD and JSON pairs)
        artifacts_by_name: Dict[str, Dict[str, Any]] = {}
        artifact_ids: Dict[str, str] = {}

        for artifact in result.artifacts:
            base_name = artifact.name
            if base_name not in artifacts_by_name:
                artifacts_by_name[base_name] = {}

            if artifact.kind == ArtifactKind.MARKDOWN:
                artifacts_by_name[base_name]["markdown"] = artifact.content
            elif artifact.kind == ArtifactKind.JSON:
                artifacts_by_name[base_name]["json"] = json.loads(artifact.content)

        # Write paired artifacts using RunManager
        for name, contents in artifacts_by_name.items():
            markdown = contents.get("markdown", "")
            json_data = contents.get("json", {})

            run.save_artifact(
                artifact_name=name,
                markdown_content=markdown,
                json_data=json_data,
                skill_name=result.skill_name,
            )

            # Generate artifact ID for claim linking
            artifact_ids[name] = f"{run.run_id}_{name}"

        return artifact_ids

    def _mark_run_failed(self, run: RunManager, issues: List[Dict[str, Any]]) -> None:
        """Mark a run as failed due to verification issues.

        Args:
            run: The run manager
            issues: List of verification issues
        """
        run.update_status(
            current_phase="failed",
            phases_completed=[],
            phases_in_progress=[],
        )

        # Log each issue
        for issue in issues:
            run.log_action(
                phase="verification",
                action=f"Verification failed: {issue.get('check', 'unknown')}",
                status="failure",
                issues_discovered=[issue.get("message", "Unknown error")],
            )
