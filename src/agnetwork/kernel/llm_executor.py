"""LLM-based skill execution for BD artifact generation.

This module provides LLM-powered implementations of each BD skill.
Each skill:
1. Builds a prompt using the prompt library
2. Calls the LLM via the adapter
3. Parses and validates the response into Pydantic models
4. Optionally runs a critic pass for quality review
5. Returns a standard SkillResult
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Type

from pydantic import BaseModel

from agnetwork.kernel.contracts import (
    ArtifactKind,
    ArtifactRef,
    Claim,
    ClaimKind,
    SkillContext,
    SkillMetrics,
    SkillResult,
)
from agnetwork.models.core import (
    FollowUpSummary,
    MeetingPrepPack,
    OutreachDraft,
    ResearchBrief,
    TargetMap,
)
from agnetwork.prompts import (
    CriticResult,
    build_critic_prompt,
    build_followup_prompt,
    build_meeting_prep_prompt,
    build_outreach_prompt,
    build_research_brief_prompt,
    build_target_map_prompt,
)
from agnetwork.prompts.critic import get_constraints_for_artifact
from agnetwork.tools.llm import LLMFactory, LLMMessage, LLMRequest
from agnetwork.tools.llm.structured import StructuredOutputError, parse_or_repair_json


class LLMSkillError(Exception):
    """Error during LLM skill execution."""

    def __init__(
        self,
        message: str,
        skill_name: str,
        original_error: Exception | None = None,
        validation_errors: list | None = None,
    ):
        super().__init__(message)
        self.skill_name = skill_name
        self.original_error = original_error
        self.validation_errors = validation_errors or []


class LLMSkillExecutor:
    """Executes BD skills using LLM generation.

    This class provides a unified interface for LLM-based skill execution.
    It handles:
    - Prompt building
    - LLM API calls
    - Response parsing and validation
    - Optional critic review
    - Artifact creation
    """

    def __init__(
        self,
        llm_factory: LLMFactory,
        enable_critic: bool = True,
        max_repairs: int = 2,
    ):
        """Initialize LLM skill executor.

        Args:
            llm_factory: Factory for LLM adapters
            enable_critic: Whether to run critic pass
            max_repairs: Maximum JSON repair attempts
        """
        self.llm_factory = llm_factory
        self.enable_critic = enable_critic
        self.max_repairs = max_repairs

    def execute_research_brief(
        self,
        inputs: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate research brief using LLM.

        Args:
            inputs: Skill inputs (company, snapshot, pains, etc.)
            context: Execution context

        Returns:
            SkillResult with artifacts and claims
        """
        company = inputs.get("company", "Unknown")
        snapshot = inputs.get("snapshot", "")
        pains = inputs.get("pains", [])
        triggers = inputs.get("triggers", [])
        competitors = inputs.get("competitors", [])
        sources = inputs.get("sources", [])

        # Build prompt
        system_prompt, user_prompt = build_research_brief_prompt(
            company=company,
            snapshot=snapshot,
            pains=pains,
            triggers=triggers,
            competitors=competitors,
            sources=sources,
        )

        # Generate and parse
        start_time = datetime.now(timezone.utc)
        data = self._generate_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=ResearchBrief,
            skill_name="research_brief",
            context=context,
        )
        end_time = datetime.now(timezone.utc)

        # Optional critic pass
        if self.enable_critic:
            data = self._run_critic_pass(
                data=data.model_dump(),
                artifact_type="research_brief",
                context=context,
                model_class=ResearchBrief,
            )

        # Create claims from personalization angles
        claims = self._extract_claims_from_angles(
            data.personalization_angles if isinstance(data, ResearchBrief) else data.get("personalization_angles", [])
        )

        # Create output
        if isinstance(data, dict):
            output = ResearchBrief.model_validate(data)
        else:
            output = data

        return self._build_skill_result(
            output=output,
            artifact_name="research_brief",
            skill_name="research_brief",
            claims=claims,
            start_time=start_time,
            end_time=end_time,
        )

    def execute_target_map(
        self,
        inputs: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate target map using LLM.

        Args:
            inputs: Skill inputs (company, etc.)
            context: Execution context

        Returns:
            SkillResult with artifacts and claims
        """
        company = inputs.get("company", "Unknown")

        # Build prompt
        system_prompt, user_prompt = build_target_map_prompt(
            company=company,
            industry=inputs.get("industry"),
            company_size=inputs.get("company_size"),
            research_context=inputs.get("research_context"),
        )

        # Generate and parse
        start_time = datetime.now(timezone.utc)
        data = self._generate_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=TargetMap,
            skill_name="target_map",
            context=context,
        )
        end_time = datetime.now(timezone.utc)

        # Optional critic pass
        if self.enable_critic:
            data = self._run_critic_pass(
                data=data.model_dump(),
                artifact_type="target_map",
                context=context,
                model_class=TargetMap,
            )

        # Create claims from personas
        claims = self._extract_claims_from_personas(
            data.personas if isinstance(data, TargetMap) else data.get("personas", [])
        )

        if isinstance(data, dict):
            output = TargetMap.model_validate(data)
        else:
            output = data

        return self._build_skill_result(
            output=output,
            artifact_name="target_map",
            skill_name="target_map",
            claims=claims,
            start_time=start_time,
            end_time=end_time,
        )

    def execute_outreach(
        self,
        inputs: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate outreach drafts using LLM.

        Args:
            inputs: Skill inputs (company, persona, channel, etc.)
            context: Execution context

        Returns:
            SkillResult with artifacts and claims
        """
        company = inputs.get("company", "Unknown")
        persona = inputs.get("persona", "Decision Maker")
        channel = inputs.get("channel", "email")

        # Build prompt
        system_prompt, user_prompt = build_outreach_prompt(
            company=company,
            persona=persona,
            channel=channel,
            research_context=inputs.get("research_context"),
            personalization_angles=inputs.get("personalization_angles"),
        )

        # Generate and parse
        start_time = datetime.now(timezone.utc)
        data = self._generate_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=OutreachDraft,
            skill_name="outreach",
            context=context,
        )
        end_time = datetime.now(timezone.utc)

        # Optional critic pass
        if self.enable_critic:
            data = self._run_critic_pass(
                data=data.model_dump(),
                artifact_type="outreach",
                context=context,
                model_class=OutreachDraft,
            )

        if isinstance(data, dict):
            output = OutreachDraft.model_validate(data)
        else:
            output = data

        return self._build_skill_result(
            output=output,
            artifact_name="outreach",
            skill_name="outreach",
            claims=[],
            start_time=start_time,
            end_time=end_time,
        )

    def execute_meeting_prep(
        self,
        inputs: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate meeting prep using LLM.

        Args:
            inputs: Skill inputs (company, meeting_type, etc.)
            context: Execution context

        Returns:
            SkillResult with artifacts and claims
        """
        company = inputs.get("company", "Unknown")
        meeting_type = inputs.get("meeting_type", "discovery")

        # Build prompt
        system_prompt, user_prompt = build_meeting_prep_prompt(
            company=company,
            meeting_type=meeting_type,
            research_context=inputs.get("research_context"),
            target_personas=inputs.get("target_personas"),
        )

        # Generate and parse
        start_time = datetime.now(timezone.utc)
        data = self._generate_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=MeetingPrepPack,
            skill_name="meeting_prep",
            context=context,
        )
        end_time = datetime.now(timezone.utc)

        # Optional critic pass
        if self.enable_critic:
            data = self._run_critic_pass(
                data=data.model_dump(),
                artifact_type="meeting_prep",
                context=context,
                model_class=MeetingPrepPack,
            )

        if isinstance(data, dict):
            output = MeetingPrepPack.model_validate(data)
        else:
            output = data

        return self._build_skill_result(
            output=output,
            artifact_name="meeting_prep",
            skill_name="meeting_prep",
            claims=[],
            start_time=start_time,
            end_time=end_time,
        )

    def execute_followup(
        self,
        inputs: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Generate follow-up using LLM.

        Args:
            inputs: Skill inputs (company, notes, etc.)
            context: Execution context

        Returns:
            SkillResult with artifacts and claims
        """
        company = inputs.get("company", "Unknown")
        notes = inputs.get("notes", "")

        # Build prompt
        system_prompt, user_prompt = build_followup_prompt(
            company=company,
            notes=notes,
            meeting_date=inputs.get("meeting_date"),
            research_context=inputs.get("research_context"),
            meeting_prep_context=inputs.get("meeting_prep_context"),
        )

        # Generate and parse
        start_time = datetime.now(timezone.utc)
        data = self._generate_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_class=FollowUpSummary,
            skill_name="followup",
            context=context,
        )
        end_time = datetime.now(timezone.utc)

        # Optional critic pass
        if self.enable_critic:
            data = self._run_critic_pass(
                data=data.model_dump(),
                artifact_type="followup",
                context=context,
                model_class=FollowUpSummary,
            )

        if isinstance(data, dict):
            output = FollowUpSummary.model_validate(data)
        else:
            output = data

        return self._build_skill_result(
            output=output,
            artifact_name="followup",
            skill_name="followup",
            claims=[],
            start_time=start_time,
            end_time=end_time,
        )

    def _generate_and_parse(
        self,
        system_prompt: str,
        user_prompt: str,
        model_class: Type[BaseModel],
        skill_name: str,
        context: SkillContext,
    ) -> BaseModel:
        """Generate LLM response and parse into model.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model_class: Target Pydantic model
            skill_name: Skill name for logging
            context: Execution context

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMSkillError: If generation or parsing fails
        """
        adapter = self.llm_factory.get(role="draft")

        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            role="draft",
            response_format="json",
            metadata={
                "run_id": context.run_id,
                "skill_name": skill_name,
            },
        )

        try:
            response = adapter.complete(request)

            # Parse and validate with repair loop
            return parse_or_repair_json(
                model=model_class,
                llm_text=response.text,
                llm_factory=self.llm_factory,
                role="critic",
                max_repairs=self.max_repairs,
                run_id=context.run_id,
                skill_name=skill_name,
            )

        except StructuredOutputError as e:
            raise LLMSkillError(
                message=f"Failed to parse {skill_name} output: {e}",
                skill_name=skill_name,
                original_error=e,
                validation_errors=e.validation_errors,
            )
        except Exception as e:
            raise LLMSkillError(
                message=f"LLM call failed for {skill_name}: {e}",
                skill_name=skill_name,
                original_error=e,
            )

    def _run_critic_pass(
        self,
        data: Dict[str, Any],
        artifact_type: str,
        context: SkillContext,
        model_class: Type[BaseModel],
    ) -> Dict[str, Any] | BaseModel:
        """Run critic review pass on generated output.

        Args:
            data: Generated data dict
            artifact_type: Type of artifact
            context: Execution context
            model_class: Target model class

        Returns:
            Possibly improved data
        """
        try:
            constraints = get_constraints_for_artifact(artifact_type)
            system_prompt, user_prompt = build_critic_prompt(
                output_json=data,
                artifact_type=artifact_type,
                constraints=constraints,
            )

            adapter = self.llm_factory.get(role="critic")
            request = LLMRequest(
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                role="critic",
                response_format="json",
                metadata={
                    "run_id": context.run_id,
                    "skill_name": artifact_type,
                    "critic_pass": True,
                },
            )

            response = adapter.complete(request)

            # Try to parse critic result
            critic_result = parse_or_repair_json(
                model=CriticResult,
                llm_text=response.text,
                llm_factory=self.llm_factory,
                role="critic",
                max_repairs=1,
            )

            # If critic provides patched JSON, use it
            if critic_result.patched_json:
                return model_class.model_validate(critic_result.patched_json)

            # Otherwise return original
            return data

        except Exception as e:
            # Critic is optional - if it fails, return original
            import logging
            logging.getLogger(__name__).debug(f"Critic pass failed: {type(e).__name__}: {e}")
            return data

    def _extract_claims_from_angles(
        self, angles: List[Dict[str, Any]]
    ) -> List[Claim]:
        """Extract claims from personalization angles."""
        claims = []
        for angle in angles:
            is_assumption = angle.get("is_assumption", True)
            claims.append(
                Claim(
                    text=angle.get("fact", ""),
                    kind=ClaimKind.ASSUMPTION if is_assumption else ClaimKind.FACT,
                    evidence=[],
                )
            )
        return claims

    def _extract_claims_from_personas(
        self, personas: List[Dict[str, Any]]
    ) -> List[Claim]:
        """Extract claims from persona hypotheses."""
        claims = []
        for persona in personas:
            is_assumption = persona.get("is_assumption", True)
            claims.append(
                Claim(
                    text=persona.get("hypothesis", ""),
                    kind=ClaimKind.ASSUMPTION if is_assumption else ClaimKind.FACT,
                    evidence=[],
                )
            )
        return claims

    def _build_skill_result(
        self,
        output: BaseModel,
        artifact_name: str,
        skill_name: str,
        claims: List[Claim],
        start_time: datetime,
        end_time: datetime,
    ) -> SkillResult:
        """Build a SkillResult from generated output.

        Args:
            output: Pydantic model output
            artifact_name: Name for artifacts
            skill_name: Skill name
            claims: List of claims
            start_time: Execution start time
            end_time: Execution end time

        Returns:
            SkillResult with artifacts
        """
        # Generate JSON content
        json_data = output.model_dump(mode="json")
        json_content = json.dumps(json_data, indent=2, default=str)

        # Generate markdown from structured data
        markdown_content = self._render_markdown(output, artifact_name)

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name=artifact_name,
                kind=ArtifactKind.MARKDOWN,
                content=markdown_content,
            ),
            ArtifactRef(
                name=artifact_name,
                kind=ArtifactKind.JSON,
                content=json_content,
            ),
        ]

        # Calculate metrics
        metrics = SkillMetrics(
            execution_time_ms=(end_time - start_time).total_seconds() * 1000,
        )

        return SkillResult(
            output=output,
            artifacts=artifacts,
            claims=claims,
            skill_name=skill_name,
            skill_version="1.0-llm",
            metrics=metrics,
        )

    def _render_markdown(self, output: BaseModel, artifact_name: str) -> str:
        """Render Pydantic model as markdown.

        Uses the same templates as manual mode for consistency.
        """
        data = output.model_dump()

        if artifact_name == "research_brief":
            return self._render_research_brief_md(data)
        elif artifact_name == "target_map":
            return self._render_target_map_md(data)
        elif artifact_name == "outreach":
            return self._render_outreach_md(data)
        elif artifact_name == "meeting_prep":
            return self._render_meeting_prep_md(data)
        elif artifact_name == "followup":
            return self._render_followup_md(data)
        else:
            return f"# {artifact_name}\n\n```json\n{json.dumps(data, indent=2)}\n```"

    def _render_research_brief_md(self, data: Dict[str, Any]) -> str:
        """Render research brief as markdown."""
        lines = [f"# Account Research Brief: {data.get('company', 'Unknown')}"]
        lines.append("")
        lines.append("## Snapshot")
        lines.append(data.get("snapshot", ""))
        lines.append("")
        lines.append("## Key Pains")
        for pain in data.get("pains", []):
            lines.append(f"- {pain}")
        lines.append("")
        lines.append("## Triggers")
        for trigger in data.get("triggers", []):
            lines.append(f"- {trigger}")
        lines.append("")
        lines.append("## Competitors")
        for comp in data.get("competitors", []):
            lines.append(f"- {comp}")
        lines.append("")
        lines.append("## Personalization Angles")
        for angle in data.get("personalization_angles", []):
            lines.append("")
            lines.append(f"### Angle: {angle.get('name', 'Unknown')}")
            assumption_tag = " (ASSUMPTION)" if angle.get("is_assumption") else ""
            lines.append(f"- **Fact**: {angle.get('fact', '')}{assumption_tag}")
        return "\n".join(lines)

    def _render_target_map_md(self, data: Dict[str, Any]) -> str:
        """Render target map as markdown."""
        lines = [f"# Target Map: {data.get('company', 'Unknown')}"]
        lines.append("")
        lines.append("## Personas")
        for persona in data.get("personas", []):
            lines.append("")
            lines.append(f"### {persona.get('title', 'Unknown')}")
            lines.append(f"- **Role**: {persona.get('role', 'unknown')}")
            lines.append(f"- **Hypothesis**: {persona.get('hypothesis', '')}")
            if persona.get("is_assumption"):
                lines.append("- _(Assumption)_")
        return "\n".join(lines)

    def _render_outreach_md(self, data: Dict[str, Any]) -> str:
        """Render outreach as markdown."""
        lines = [f"# Outreach: {data.get('company', 'Unknown')}"]
        lines.append("")
        for variant in data.get("variants", []):
            channel = variant.get("channel", "email")
            lines.append(f"## {channel.title()} Draft")
            lines.append("")
            if variant.get("subject_or_hook"):
                lines.append(f"**Subject/Hook**: {variant['subject_or_hook']}")
                lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(variant.get("body", ""))
            lines.append("")
            lines.append("---")
            if variant.get("personalization_notes"):
                lines.append("")
                lines.append(f"**Personalization Notes**: {variant['personalization_notes']}")
            lines.append("")
        lines.append("## Follow-up Sequence")
        for i, step in enumerate(data.get("sequence_steps", []), 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        lines.append("## Objection Responses")
        for obj, resp in data.get("objection_responses", {}).items():
            lines.append(f"- **{obj}**: {resp}")
        return "\n".join(lines)

    def _render_meeting_prep_md(self, data: Dict[str, Any]) -> str:
        """Render meeting prep as markdown."""
        lines = [f"# Meeting Prep: {data.get('company', 'Unknown')}"]
        lines.append("")
        lines.append(f"## Meeting Type: {data.get('meeting_type', 'discovery').title()}")
        lines.append("")
        lines.append("## Agenda")
        for i, item in enumerate(data.get("agenda", []), 1):
            lines.append(f"{i}. {item}")
        lines.append("")
        lines.append("## Discovery Questions")
        for q in data.get("questions", []):
            lines.append(f"- {q}")
        lines.append("")
        lines.append("## Stakeholder Map")
        for title, role in data.get("stakeholder_map", {}).items():
            lines.append(f"- **{title}**: {role}")
        lines.append("")
        lines.append("## Listen For")
        for signal in data.get("listen_for_signals", []):
            lines.append(f"- {signal}")
        lines.append("")
        lines.append("## Close Plan")
        lines.append(data.get("close_plan", ""))
        return "\n".join(lines)

    def _render_followup_md(self, data: Dict[str, Any]) -> str:
        """Render follow-up as markdown."""
        lines = [f"# Follow-up: {data.get('company', 'Unknown')}"]
        lines.append("")
        lines.append("## Meeting Summary")
        lines.append(data.get("summary", ""))
        lines.append("")
        lines.append("## Next Steps")
        for i, step in enumerate(data.get("next_steps", []), 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        lines.append("## Action Items")
        for task in data.get("tasks", []):
            lines.append(
                f"- **{task.get('task', '')}** - Owner: {task.get('owner', 'unknown')} - Due: {task.get('due', 'TBD')}"
            )
        lines.append("")
        lines.append("## CRM Notes")
        lines.append("```")
        lines.append(data.get("crm_notes", ""))
        lines.append("```")
        return "\n".join(lines)


# Skill name to executor method mapping
SKILL_EXECUTORS = {
    "research_brief": "execute_research_brief",
    "target_map": "execute_target_map",
    "outreach": "execute_outreach",
    "meeting_prep": "execute_meeting_prep",
    "followup": "execute_followup",
}
