"""Source ingestion tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

from agnetwork.storage.sqlite import SQLiteManager

if TYPE_CHECKING:
    from agnetwork.workspaces.context import WorkspaceContext


class SourceIngestor:
    """Handles ingestion of sources (URLs, pasted text, files).

    IMPORTANT: Requires a WorkspaceContext for workspace-scoped storage.
    """

    def __init__(self, run_dir: Path, ws_ctx: "WorkspaceContext"):
        """Initialize with run directory and workspace context.

        Args:
            run_dir: Path to the run directory for storing sources.
            ws_ctx: WorkspaceContext for database access.
        """
        self.run_dir = run_dir
        self.sources_dir = run_dir / "sources"
        self.sources_dir.mkdir(exist_ok=True)
        self.ws_ctx = ws_ctx
        self.db = SQLiteManager.for_workspace(ws_ctx)
        self.ingested_sources: List[Dict] = []

    def ingest_text(
        self, content: str, title: Optional[str] = None, company: Optional[str] = None
    ) -> str:
        """Ingest pasted text as a source."""
        source_id = f"src_{uuid4().hex[:8]}"
        source_file = self.sources_dir / f"{source_id}.json"

        source_data = {
            "id": source_id,
            "source_type": "pasted_text",
            "title": title or "Pasted text",
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"company": company} if company else {},
        }

        with open(source_file, "w") as f:
            json.dump(source_data, f, indent=2)

        # Store in database
        metadata = source_data.get("metadata", {})
        self.db.insert_source(
            source_id,
            "pasted_text",
            content,
            title=title,
            metadata=metadata,
        )

        self.ingested_sources.append(source_data)
        return source_id

    def ingest_file(self, file_path: Path, company: Optional[str] = None) -> str:
        """Ingest a file as a source."""
        source_id = f"src_{uuid4().hex[:8]}"
        source_file = self.sources_dir / f"{source_id}.json"

        # Read file content
        with open(file_path, "r") as f:
            content = f.read()

        source_data = {
            "id": source_id,
            "source_type": "file",
            "title": file_path.name,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"original_path": str(file_path), "company": company},
        }

        with open(source_file, "w") as f:
            json.dump(source_data, f, indent=2)

        # Store in database
        metadata = source_data.get("metadata", {})
        self.db.insert_source(
            source_id,
            "file",
            content,
            title=file_path.name,
            metadata=metadata,
        )

        self.ingested_sources.append(source_data)
        return source_id

    def ingest_url(
        self, url: str, title: Optional[str] = None, company: Optional[str] = None
    ) -> str:
        """Ingest a URL as a source (placeholder for future web scraping)."""
        source_id = f"src_{uuid4().hex[:8]}"
        source_file = self.sources_dir / f"{source_id}.json"

        # TODO: Implement actual web scraping in v0.2
        content = f"[URL source] {url}\n\nContent not yet fetched (feature coming in v0.2)"

        source_data = {
            "id": source_id,
            "source_type": "url",
            "title": title or url,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"url": url, "company": company},
        }

        with open(source_file, "w") as f:
            json.dump(source_data, f, indent=2)

        # Store in database
        metadata = source_data.get("metadata", {})
        self.db.insert_source(
            source_id,
            "url",
            content,
            title=title or url,
            metadata=metadata,
        )

        self.ingested_sources.append(source_data)
        return source_id

    def get_ingested_sources(self) -> List[Dict]:
        """Return list of ingested sources."""
        return self.ingested_sources
