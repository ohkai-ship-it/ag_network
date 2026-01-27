"""Memory API for AG Network.

This module provides the Memory API for retrieval over stored sources
and artifacts using FTS5 full-text search.

M4 focus: RAG Phase 1 - fast, reliable search + retrieval.
No embeddings/vector DB (that's M8).

Key components:
- SourceHit/ArtifactHit: Search result types
- EvidenceBundle: Container for retrieved context
- search_sources/search_artifacts: FTS-backed search functions
- retrieve_context: Get relevant context for a task
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agnetwork.storage.sqlite import SQLiteManager


@dataclass
class SourceHit:
    """A search hit from source FTS search.

    Attributes:
        id: Source ID
        score: FTS relevance score (lower is better for BM25)
        excerpt: Highlighted excerpt from content
        title: Source title
        uri: Source URI/URL
        source_type: Type of source (url, text, file)
        created_at: When the source was created
        metadata: Additional metadata dict
    """

    id: str
    score: float
    excerpt: str
    title: Optional[str] = None
    uri: Optional[str] = None
    source_type: str = "unknown"
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactHit:
    """A search hit from artifact FTS search.

    Attributes:
        id: Artifact ID
        score: FTS relevance score (lower is better for BM25)
        excerpt: Highlighted excerpt from content
        name: Artifact name
        artifact_type: Type of artifact (research_brief, target_map, etc.)
        run_id: Run ID that created this artifact
        company_id: Associated company ID
        created_at: When the artifact was created
    """

    id: str
    score: float
    excerpt: str
    name: Optional[str] = None
    artifact_type: str = "unknown"
    run_id: Optional[str] = None
    company_id: Optional[str] = None
    created_at: Optional[str] = None


class SourceRef(BaseModel):
    """Lightweight reference to a source for evidence bundles.

    This is used in EvidenceBundle to provide context without
    including full source content.
    """

    source_id: str
    source_type: str = "unknown"
    title: Optional[str] = None
    uri: Optional[str] = None
    excerpt: Optional[str] = None
    score: Optional[float] = None


class ArtifactSummary(BaseModel):
    """Lightweight summary of an artifact for evidence bundles.

    Provides artifact metadata and excerpt without full content.
    """

    artifact_id: str
    name: Optional[str] = None
    artifact_type: str = "unknown"
    run_id: Optional[str] = None
    company_id: Optional[str] = None
    excerpt: Optional[str] = None
    score: Optional[float] = None


class EvidenceBundle(BaseModel):
    """Bundle of evidence (sources + artifacts) for kernel use.

    Contains retrieved context that can be passed to skills
    for evidence-backed generation.

    Attributes:
        sources: List of source references with excerpts
        artifacts: List of artifact summaries
        query: The query used to retrieve this evidence
        retrieval_timestamp: When this bundle was created
    """

    sources: List[SourceRef] = Field(default_factory=list)
    artifacts: List[ArtifactSummary] = Field(default_factory=list)
    query: Optional[str] = None
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def source_ids(self) -> List[str]:
        """Get list of source IDs in this bundle."""
        return [s.source_id for s in self.sources]

    @property
    def artifact_ids(self) -> List[str]:
        """Get list of artifact IDs in this bundle."""
        return [a.artifact_id for a in self.artifacts]

    def is_empty(self) -> bool:
        """Check if bundle has no evidence."""
        return len(self.sources) == 0 and len(self.artifacts) == 0


class MemoryAPI:
    """Memory API for retrieval over stored sources and artifacts.

    Provides FTS5-backed search and retrieval functions for the kernel.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize Memory API.

        Args:
            db_path: Path to SQLite database. Defaults to config.db_path.
        """
        self.db = SQLiteManager(db_path)

    def search_sources(
        self,
        query: str,
        *,
        limit: int = 10,
        workspace: Optional[str] = None,
    ) -> List[SourceHit]:
        """Search sources using FTS5 full-text search.

        Args:
            query: Search query (supports FTS5 syntax)
            limit: Maximum results to return
            workspace: Optional workspace filter (not yet implemented)

        Returns:
            List of SourceHit objects ordered by relevance
        """
        if not query or not query.strip():
            return []

        # Escape special FTS5 characters for safety
        safe_query = self._escape_fts_query(query)

        try:
            results = self.db.search_sources_fts(safe_query, limit=limit)
        except Exception:
            # If FTS query fails, try a simpler query
            safe_query = self._to_simple_query(query)
            try:
                results = self.db.search_sources_fts(safe_query, limit=limit)
            except Exception:
                return []

        return [
            SourceHit(
                id=r["id"],
                score=r.get("score", 0.0),
                excerpt=r.get("excerpt", ""),
                title=r.get("title"),
                uri=r.get("uri"),
                source_type=r.get("source_type", "unknown"),
                created_at=r.get("created_at"),
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]

    def search_artifacts(
        self,
        query: str,
        *,
        limit: int = 10,
        workspace: Optional[str] = None,
    ) -> List[ArtifactHit]:
        """Search artifacts using FTS5 full-text search.

        Args:
            query: Search query (supports FTS5 syntax)
            limit: Maximum results to return
            workspace: Optional workspace filter (not yet implemented)

        Returns:
            List of ArtifactHit objects ordered by relevance
        """
        if not query or not query.strip():
            return []

        safe_query = self._escape_fts_query(query)

        try:
            results = self.db.search_artifacts_fts(safe_query, limit=limit)
        except Exception:
            safe_query = self._to_simple_query(query)
            try:
                results = self.db.search_artifacts_fts(safe_query, limit=limit)
            except Exception:
                return []

        return [
            ArtifactHit(
                id=r["id"],
                score=r.get("score", 0.0),
                excerpt=r.get("excerpt", ""),
                name=r.get("name"),
                artifact_type=r.get("artifact_type", "unknown"),
                run_id=r.get("run_id"),
                company_id=r.get("company_id"),
                created_at=r.get("created_at"),
            )
            for r in results
        ]

    def retrieve_context(
        self,
        task_spec: Any,
        *,
        limit_sources: int = 10,
        limit_artifacts: int = 10,
    ) -> EvidenceBundle:
        """Retrieve relevant context for a task specification.

        Builds a search query from the task spec and retrieves
        relevant sources and artifacts.

        Args:
            task_spec: TaskSpec with inputs to build query from
            limit_sources: Max sources to retrieve
            limit_artifacts: Max artifacts to retrieve

        Returns:
            EvidenceBundle with retrieved sources and artifacts
        """
        # Build query from task spec
        query = self._build_query_from_task_spec(task_spec)

        if not query:
            return EvidenceBundle(query=query)

        # Search sources
        source_hits = self.search_sources(query, limit=limit_sources)
        source_refs = [
            SourceRef(
                source_id=hit.id,
                source_type=hit.source_type,
                title=hit.title,
                uri=hit.uri,
                excerpt=hit.excerpt,
                score=hit.score,
            )
            for hit in source_hits
        ]

        # Search artifacts
        artifact_hits = self.search_artifacts(query, limit=limit_artifacts)
        artifact_summaries = [
            ArtifactSummary(
                artifact_id=hit.id,
                name=hit.name,
                artifact_type=hit.artifact_type,
                run_id=hit.run_id,
                company_id=hit.company_id,
                excerpt=hit.excerpt,
                score=hit.score,
            )
            for hit in artifact_hits
        ]

        return EvidenceBundle(
            sources=source_refs,
            artifacts=artifact_summaries,
            query=query,
        )

    def get_source_content(self, source_id: str) -> Optional[str]:
        """Get full content of a source by ID.

        Args:
            source_id: Source ID to retrieve

        Returns:
            Source content string or None if not found
        """
        source = self.db.get_source(source_id)
        if source:
            return source.get("content")
        return None

    def _build_query_from_task_spec(self, task_spec: Any) -> str:
        """Build a search query from a task specification.

        Extracts relevant terms from task spec inputs to form
        a search query.

        Args:
            task_spec: TaskSpec with inputs

        Returns:
            Search query string
        """
        inputs = getattr(task_spec, "inputs", {})
        if not inputs:
            return ""

        # Extract key terms
        terms = []

        # Company name is usually the most important
        company = inputs.get("company")
        if company:
            terms.append(company)

        # Add other relevant fields
        for field_name in ["snapshot", "persona"]:
            value = inputs.get(field_name)
            if value and isinstance(value, str):
                terms.append(value)

        # Add list fields
        for list_field in ["pains", "triggers", "competitors"]:
            values = inputs.get(list_field)
            if values and isinstance(values, list):
                terms.extend(str(v) for v in values[:3])  # Limit to first 3

        if not terms:
            return ""

        # Join with OR for broader matching
        return " OR ".join(terms)

    def _escape_fts_query(self, query: str) -> str:
        """Escape special FTS5 characters in query.

        Args:
            query: Raw query string

        Returns:
            Escaped query safe for FTS5
        """
        # Remove characters that have special meaning in FTS5
        special_chars = ['"', "'", "(", ")", "*", "^", ":", "-"]
        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, " ")
        # Collapse multiple spaces
        return " ".join(escaped.split())

    def _to_simple_query(self, query: str) -> str:
        """Convert query to simple word-based query.

        Falls back to this if FTS query fails.

        Args:
            query: Original query

        Returns:
            Simple word-based query
        """
        words = query.split()
        # Filter to alphanumeric words only
        safe_words = [w for w in words if w.isalnum()]
        if not safe_words:
            return ""
        return " OR ".join(safe_words[:5])  # Limit to 5 words


# Module-level convenience functions

_memory_api: Optional[MemoryAPI] = None


def get_memory_api(db_path: Optional[Path] = None) -> MemoryAPI:
    """Get or create the global MemoryAPI instance.

    Args:
        db_path: Optional database path (only used on first call)

    Returns:
        MemoryAPI instance
    """
    global _memory_api
    if _memory_api is None:
        _memory_api = MemoryAPI(db_path)
    return _memory_api


def search_sources(
    query: str,
    *,
    limit: int = 10,
    workspace: Optional[str] = None,
) -> List[SourceHit]:
    """Search sources using FTS5 full-text search.

    Convenience wrapper around MemoryAPI.search_sources.

    Args:
        query: Search query
        limit: Maximum results
        workspace: Optional workspace filter

    Returns:
        List of SourceHit objects
    """
    return get_memory_api().search_sources(query, limit=limit, workspace=workspace)


def search_artifacts(
    query: str,
    *,
    limit: int = 10,
    workspace: Optional[str] = None,
) -> List[ArtifactHit]:
    """Search artifacts using FTS5 full-text search.

    Convenience wrapper around MemoryAPI.search_artifacts.

    Args:
        query: Search query
        limit: Maximum results
        workspace: Optional workspace filter

    Returns:
        List of ArtifactHit objects
    """
    return get_memory_api().search_artifacts(query, limit=limit, workspace=workspace)


def retrieve_context(
    task_spec: Any,
    *,
    limit_sources: int = 10,
    limit_artifacts: int = 10,
) -> EvidenceBundle:
    """Retrieve relevant context for a task specification.

    Convenience wrapper around MemoryAPI.retrieve_context.

    Args:
        task_spec: TaskSpec to retrieve context for
        limit_sources: Max sources
        limit_artifacts: Max artifacts

    Returns:
        EvidenceBundle with retrieved evidence
    """
    return get_memory_api().retrieve_context(
        task_spec,
        limit_sources=limit_sources,
        limit_artifacts=limit_artifacts,
    )
