"""Mapping layer: BD pipeline artifacts → CRM objects.

Converts completed pipeline runs into canonical CRM objects:
- Account (from company inputs)
- Contacts (from target_map personas)
- Activities (from outreach, meeting_prep, followup artifacts)

Each activity carries full traceability:
- run_id: Links back to the pipeline run
- artifact_refs: Paths to artifact files
- source_ids: Evidence scoped to each artifact (M6.1)

M6: No artifact schema changes required. Works with existing artifacts.
M6.1: Deterministic IDs for idempotent imports, activity-level evidence scoping.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agnetwork.config import config
from agnetwork.crm.ids import make_account_id, make_activity_id, make_contact_id
from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityDirection,
    ActivityType,
    Contact,
    CRMExportManifest,
    CRMExportPackage,
)
from agnetwork.storage.sqlite import SQLiteManager, normalize_source_ids


class PipelineMapper:
    """Maps BD pipeline runs to CRM objects.

    Takes a completed pipeline run (run_id, artifacts, claims) and
    produces a CRMExportPackage with:
    - Account (from company)
    - Contacts (from target personas)
    - Activities (from outreach/meeting_prep/followup)

    All objects carry full traceability to sources and artifacts.
    """

    def __init__(self, db: Optional[SQLiteManager] = None):
        """Initialize the mapper.

        Args:
            db: SQLiteManager for querying claims/sources. Creates new one if not provided.
        """
        self.db = db or SQLiteManager()

    def map_run(
        self,
        run_id: str,
        run_dir: Optional[Path] = None,
        company: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> CRMExportPackage:
        """Map a pipeline run to CRM objects.

        Args:
            run_id: Run ID to map
            run_dir: Path to run directory (auto-detected if not provided)
            company: Company name (read from inputs.json if not provided)
            domain: Company domain (optional)

        Returns:
            CRMExportPackage with mapped objects
        """
        # Resolve run directory
        if run_dir is None:
            run_dir = config.runs_dir / run_id

        if not run_dir.exists():
            raise ValueError(f"Run directory not found: {run_dir}")

        # Load inputs
        inputs = self._load_inputs(run_dir)
        company = company or inputs.get("company", "Unknown")

        # Load artifacts
        artifacts = self._load_artifacts(run_dir)

        # Get claims and source_ids for this run
        all_source_ids: Set[str] = set()
        claim_count = 0

        # Collect source_ids from artifacts (M4/M5: embedded in JSON)
        for artifact_data in artifacts.values():
            if isinstance(artifact_data, dict):
                # Check meta for embedded source_ids
                if "source_ids" in artifact_data:
                    all_source_ids.update(normalize_source_ids(artifact_data["source_ids"]))

                # Check personalization_angles for source_ids
                for angle in artifact_data.get("personalization_angles", []):
                    if "source_ids" in angle:
                        all_source_ids.update(normalize_source_ids(angle["source_ids"]))

        # Query claims from database for this run's artifacts
        db_artifacts = self.db.get_artifacts_by_run(run_id)
        for db_artifact in db_artifacts:
            claims = self.db.get_claims_by_artifact(db_artifact["id"])
            claim_count += len(claims)
            for claim in claims:
                all_source_ids.update(claim.get("source_ids", []))

        # Also check inputs for captured source_ids
        input_source_ids = inputs.get("source_ids", [])
        all_source_ids.update(input_source_ids)

        # Sort source_ids for stability
        sorted_source_ids = sorted(all_source_ids)

        # Create account
        account = self._create_account(company, domain, inputs, sorted_source_ids)

        # Create contacts from target_map
        contacts = self._create_contacts(
            account.account_id,
            artifacts.get("target_map", {}),
        )

        # Create activities from artifacts
        activities = self._create_activities(
            account.account_id,
            contacts,
            artifacts,
            run_id,
            run_dir,
            sorted_source_ids,
        )

        # Build manifest
        manifest = CRMExportManifest(
            export_id=f"export_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            crm_export_version="1.0",
            run_id=run_id,
            company=company,
            account_count=1,
            contact_count=len(contacts),
            activity_count=len(activities),
            artifact_refs=list(artifacts.keys()),
            source_count=len(sorted_source_ids),
            claim_count=claim_count,
            run_source_ids=sorted_source_ids,  # M6.1: Run-level evidence union
            files=["manifest.json", "accounts.json", "contacts.json", "activities.json"],
        )

        return CRMExportPackage(
            manifest=manifest,
            accounts=[account],
            contacts=contacts,
            activities=activities,
        )

    def _load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load inputs.json from run directory."""
        inputs_file = run_dir / "inputs.json"
        if inputs_file.exists():
            with open(inputs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_artifacts(self, run_dir: Path) -> Dict[str, Dict[str, Any]]:
        """Load all artifact JSON files from run directory."""
        artifacts_dir = run_dir / "artifacts"
        artifacts = {}

        if not artifacts_dir.exists():
            return artifacts

        for json_file in artifacts_dir.glob("*.json"):
            artifact_name = json_file.stem
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    artifacts[artifact_name] = json.load(f)
                except json.JSONDecodeError:
                    pass  # Skip invalid JSON

        return artifacts

    def _create_account(
        self,
        company: str,
        domain: Optional[str],
        inputs: Dict[str, Any],
        source_ids: List[str],
    ) -> Account:
        """Create Account from company information.

        M6.1: Uses deterministic ID based on domain (preferred) or company name.
        """
        # M6.1: Generate deterministic account_id
        location = inputs.get("location")
        account_id = make_account_id(domain=domain, name=company, location=location)

        # Extract description from snapshot
        description = inputs.get("snapshot", "")

        # Extract tags from pains, triggers, etc.
        tags = []
        if inputs.get("pains"):
            tags.extend([f"pain:{p}" for p in inputs["pains"][:3]])
        if inputs.get("triggers"):
            tags.extend([f"trigger:{t}" for t in inputs["triggers"][:3]])

        return Account(
            account_id=account_id,
            name=company,
            domain=domain,
            description=description,
            tags=tags,
            metadata={
                "source_ids": source_ids,
                "competitors": inputs.get("competitors", []),
            },
        )

    def _create_contacts(
        self,
        account_id: str,
        target_map: Dict[str, Any],
    ) -> List[Contact]:
        """Create Contacts from target_map personas.

        M6.1: Uses deterministic IDs based on account + name + role.
        """
        contacts = []

        personas = target_map.get("personas", [])
        for i, persona in enumerate(personas):
            title = persona.get("title", f"Contact {i+1}")
            role = persona.get("role", "")
            hypothesis = persona.get("hypothesis", "")
            email = persona.get("email")  # May be present in enriched data

            # M6.1: Generate deterministic contact_id
            contact_id = make_contact_id(
                email=email,
                account_id=account_id,
                full_name=title,
                role_title=role or title,
            )

            contacts.append(
                Contact(
                    contact_id=contact_id,
                    account_id=account_id,
                    full_name=title,  # Use title as placeholder name
                    role_title=title,
                    email=email,
                    persona_type=role,
                    hypothesis=hypothesis,
                    tags=[f"persona:{role}"] if role else [],
                )
            )

        # If no personas, create a placeholder with deterministic ID
        if not contacts:
            placeholder_id = make_contact_id(
                account_id=account_id,
                full_name="Primary Contact",
                role_title="primary",
            )
            contacts.append(
                Contact(
                    contact_id=placeholder_id,
                    account_id=account_id,
                    full_name="Primary Contact",
                    role_title="",
                    tags=["placeholder"],
                )
            )

        return contacts

    def _extract_artifact_source_ids(
        self,
        artifact_data: Dict[str, Any],
        artifact_name: str,
        run_id: str,
    ) -> List[str]:
        """Extract source_ids scoped to a specific artifact.

        M6.1: Each activity gets only the evidence relevant to its artifact,
        not the full run's evidence set.

        Args:
            artifact_data: The artifact JSON data
            artifact_name: Name of the artifact (e.g., "outreach")
            run_id: Run ID for database queries

        Returns:
            Sorted list of source_ids for this artifact
        """
        source_ids: Set[str] = set()

        # 1. Check embedded source_ids in artifact
        if "source_ids" in artifact_data:
            source_ids.update(normalize_source_ids(artifact_data["source_ids"]))

        # 2. Check personalization_angles for source_ids (common in research_brief)
        for angle in artifact_data.get("personalization_angles", []):
            if "source_ids" in angle:
                source_ids.update(normalize_source_ids(angle["source_ids"]))

        # 3. Check claims for source_ids (from meta block)
        meta = artifact_data.get("meta", {})
        if "source_ids" in meta:
            source_ids.update(normalize_source_ids(meta["source_ids"]))

        # 4. Fallback: Query claims from database for this artifact
        if not source_ids:
            db_artifacts = self.db.get_artifacts_by_run(run_id)
            for db_artifact in db_artifacts:
                if artifact_name in db_artifact.get("name", ""):
                    claims = self.db.get_claims_by_artifact(db_artifact["id"])
                    for claim in claims:
                        source_ids.update(claim.get("source_ids", []))

        return sorted(source_ids)

    def _get_scoped_source_ids(
        self,
        artifact_data: Dict[str, Any],
        artifact_ref: str,
        run_id: str,
        fallback_source_ids: List[str],
    ) -> List[str]:
        """Get source_ids scoped to artifact, with fallback."""
        scoped = self._extract_artifact_source_ids(artifact_data, artifact_ref, run_id)
        return scoped if scoped else fallback_source_ids

    def _activity_from_outreach(
        self,
        outreach: Dict[str, Any],
        account_id: str,
        contact_id: Optional[str],
        run_id: str,
        run_dir: Path,
        all_source_ids: List[str],
    ) -> Activity:
        """Create Activity from outreach artifact."""
        artifact_ref = "outreach"
        channel = outreach.get("channel", "email")
        activity_type = ActivityType.EMAIL if channel == "email" else ActivityType.LINKEDIN

        return Activity(
            activity_id=make_activity_id(run_id=run_id, artifact_ref=artifact_ref, activity_type=activity_type.value),
            account_id=account_id,
            contact_id=contact_id,
            activity_type=activity_type,
            subject=outreach.get("subject_or_hook", f"Outreach to {outreach.get('company', 'company')}"),
            body=outreach.get("body", ""),
            direction=ActivityDirection.OUTBOUND,
            run_id=run_id,
            artifact_refs=[str(run_dir / "artifacts" / "outreach.json")],
            source_ids=self._get_scoped_source_ids(outreach, artifact_ref, run_id, all_source_ids),
            metadata={
                "artifact_type": "outreach",
                "persona": outreach.get("persona", ""),
                "channel": channel,
                "personalization_notes": outreach.get("personalization_notes", ""),
                "sequence_steps": outreach.get("sequence_steps", []),
                "objection_responses": outreach.get("objection_responses", {}),
            },
        )

    def _activity_from_meeting_prep(
        self,
        prep: Dict[str, Any],
        account_id: str,
        contact_id: Optional[str],
        run_id: str,
        run_dir: Path,
        all_source_ids: List[str],
    ) -> Activity:
        """Create Activity from meeting_prep artifact."""
        artifact_ref = "meeting_prep"
        agenda = prep.get("agenda", [])
        questions = prep.get("questions", [])

        body_parts = []
        if agenda:
            body_parts.append("## Agenda\n" + "\n".join(f"- {item}" for item in agenda))
        if questions:
            body_parts.append("## Questions\n" + "\n".join(f"- {q}" for q in questions))

        return Activity(
            activity_id=make_activity_id(run_id=run_id, artifact_ref=artifact_ref, activity_type=ActivityType.NOTE.value),
            account_id=account_id,
            contact_id=contact_id,
            activity_type=ActivityType.NOTE,
            subject=f"Meeting Prep: {prep.get('meeting_type', 'discovery').title()}",
            body="\n\n".join(body_parts),
            direction=ActivityDirection.OUTBOUND,
            run_id=run_id,
            artifact_refs=[str(run_dir / "artifacts" / "meeting_prep.json")],
            source_ids=self._get_scoped_source_ids(prep, artifact_ref, run_id, all_source_ids),
            metadata={
                "artifact_type": "meeting_prep",
                "meeting_type": prep.get("meeting_type", ""),
                "stakeholder_map": prep.get("stakeholder_map", {}),
            },
        )

    def _activity_from_followup(
        self,
        followup: Dict[str, Any],
        account_id: str,
        contact_id: Optional[str],
        run_id: str,
        run_dir: Path,
        all_source_ids: List[str],
    ) -> Activity:
        """Create Activity from followup artifact."""
        artifact_ref = "followup"
        next_steps = followup.get("next_steps", [])
        tasks = followup.get("tasks", [])

        body_parts = [followup.get("summary", "")]
        if next_steps:
            body_parts.append("## Next Steps\n" + "\n".join(f"- {step}" for step in next_steps))
        if tasks:
            body_parts.append("## Tasks\n" + "\n".join(
                f"- {t.get('task', '')} (Owner: {t.get('owner', 'TBD')})" for t in tasks
            ))

        return Activity(
            activity_id=make_activity_id(run_id=run_id, artifact_ref=artifact_ref, activity_type=ActivityType.EMAIL.value),
            account_id=account_id,
            contact_id=contact_id,
            activity_type=ActivityType.EMAIL,
            subject=f"Follow-up: {followup.get('company', 'company')}",
            body="\n\n".join(body_parts),
            direction=ActivityDirection.OUTBOUND,
            run_id=run_id,
            artifact_refs=[str(run_dir / "artifacts" / "followup.json")],
            source_ids=self._get_scoped_source_ids(followup, artifact_ref, run_id, all_source_ids),
            metadata={
                "artifact_type": "followup",
                "crm_notes": followup.get("crm_notes", ""),
            },
        )

    def _activity_from_research_brief(
        self,
        brief: Dict[str, Any],
        account_id: str,
        run_id: str,
        run_dir: Path,
        all_source_ids: List[str],
    ) -> Activity:
        """Create Activity from research_brief artifact."""
        artifact_ref = "research_brief"
        pains = brief.get("pains", [])
        triggers = brief.get("triggers", [])
        angles = brief.get("personalization_angles", [])

        body_parts = []
        if brief.get("snapshot"):
            body_parts.append(f"## Company Snapshot\n{brief['snapshot']}")
        if pains:
            body_parts.append("## Key Pains\n" + "\n".join(f"- {p}" for p in pains))
        if triggers:
            body_parts.append("## Triggers\n" + "\n".join(f"- {t}" for t in triggers))
        if angles:
            body_parts.append("## Personalization Angles\n" + "\n".join(
                f"- {a.get('name', '')}: {a.get('fact', '')}" for a in angles
            ))

        return Activity(
            activity_id=make_activity_id(run_id=run_id, artifact_ref=artifact_ref, activity_type=ActivityType.NOTE.value),
            account_id=account_id,
            contact_id=None,  # Research is at account level
            activity_type=ActivityType.NOTE,
            subject=f"Research Brief: {brief.get('company', 'company')}",
            body="\n\n".join(body_parts),
            direction=ActivityDirection.OUTBOUND,
            run_id=run_id,
            artifact_refs=[str(run_dir / "artifacts" / "research_brief.json")],
            source_ids=self._get_scoped_source_ids(brief, artifact_ref, run_id, all_source_ids),
            metadata={
                "artifact_type": "research_brief",
                "competitors": brief.get("competitors", []),
            },
        )

    def _create_activities(
        self,
        account_id: str,
        contacts: List[Contact],
        artifacts: Dict[str, Dict[str, Any]],
        run_id: str,
        run_dir: Path,
        all_source_ids: List[str],
    ) -> List[Activity]:
        """Create Activities from pipeline artifacts.

        M6.1: Uses deterministic IDs and artifact-scoped evidence.
        """
        activities = []
        primary_contact_id = contacts[0].contact_id if contacts else None

        if "outreach" in artifacts:
            activities.append(self._activity_from_outreach(
                artifacts["outreach"], account_id, primary_contact_id, run_id, run_dir, all_source_ids
            ))

        if "meeting_prep" in artifacts:
            activities.append(self._activity_from_meeting_prep(
                artifacts["meeting_prep"], account_id, primary_contact_id, run_id, run_dir, all_source_ids
            ))

        if "followup" in artifacts:
            activities.append(self._activity_from_followup(
                artifacts["followup"], account_id, primary_contact_id, run_id, run_dir, all_source_ids
            ))

        if "research_brief" in artifacts:
            activities.append(self._activity_from_research_brief(
                artifacts["research_brief"], account_id, run_id, run_dir, all_source_ids
            ))

        return activities


def map_run_to_crm(
    run_id: str,
    run_dir: Optional[Path] = None,
    company: Optional[str] = None,
    domain: Optional[str] = None,
) -> CRMExportPackage:
    """Convenience function to map a run to CRM objects.

    Args:
        run_id: Run ID to map
        run_dir: Path to run directory
        company: Company name
        domain: Company domain

    Returns:
        CRMExportPackage with mapped objects
    """
    mapper = PipelineMapper()
    return mapper.map_run(run_id, run_dir, company, domain)
