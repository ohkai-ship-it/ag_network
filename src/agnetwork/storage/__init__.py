"""Storage package for AG Network.

Provides SQLite-based persistence for sources, artifacts, companies, and claims.
Includes FTS5 full-text search support for memory retrieval.
"""

from agnetwork.storage.memory import (
    ArtifactHit,
    ArtifactSummary,
    EvidenceBundle,
    MemoryAPI,
    SourceHit,
    SourceRef,
    get_memory_api,
    retrieve_context,
    search_artifacts,
    search_sources,
)
from agnetwork.storage.sqlite import (
    SQLiteManager,
    normalize_source_ids,
    serialize_source_ids,
)

__all__ = [
    # SQLite manager
    "SQLiteManager",
    "normalize_source_ids",
    "serialize_source_ids",
    # Memory API
    "MemoryAPI",
    "get_memory_api",
    "search_sources",
    "search_artifacts",
    "retrieve_context",
    # Hit types
    "SourceHit",
    "ArtifactHit",
    "SourceRef",
    "ArtifactSummary",
    "EvidenceBundle",
]
