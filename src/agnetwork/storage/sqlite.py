"""SQLite database operations for AG Network.

This module provides SQLite-based storage for:
- Sources: Raw source material (text, URLs, files)
- Companies: Company entities
- Artifacts: Generated artifacts (research briefs, target maps, etc.)
- Claims: Traceability linking artifacts to sources via evidence

M4 additions:
- FTS5 full-text search for sources and artifacts
- Normalized JSON array storage for claims.source_ids
- Memory retrieval API support

M5 additions:
- Source upsert with content_hash deduplication
- run_id linkage for sources
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agnetwork.config import config


def normalize_source_ids(source_ids: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize source_ids to a list of strings.

    Handles legacy formats:
    - CSV strings: "src_1,src_2" -> ["src_1", "src_2"]
    - JSON arrays: '["src_1","src_2"]' -> ["src_1", "src_2"]
    - Already a list: ["src_1"] -> ["src_1"]
    - None: None -> []

    Args:
        source_ids: Source IDs in various formats

    Returns:
        Normalized list of source IDs
    """
    if source_ids is None:
        return []

    if isinstance(source_ids, list):
        return source_ids

    if not isinstance(source_ids, str):
        return []

    source_ids = source_ids.strip()
    if not source_ids:
        return []

    # Try parsing as JSON first
    if source_ids.startswith("["):
        try:
            parsed = json.loads(source_ids)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass

    # Fall back to CSV parsing
    return [s.strip() for s in source_ids.split(",") if s.strip()]


def serialize_source_ids(source_ids: Optional[List[str]]) -> str:
    """Serialize source_ids to canonical JSON array string.

    Args:
        source_ids: List of source IDs

    Returns:
        JSON array string, e.g., '["src_1","src_2"]'
    """
    if source_ids is None:
        return "[]"
    return json.dumps(source_ids)


class SQLiteManager:
    """Manages SQLite database for entities and traceability.

    Provides CRUD operations for sources, companies, artifacts, and claims.
    Includes FTS5 full-text search support for memory retrieval.

    Supports context manager protocol for automatic cleanup:
        with SQLiteManager(db_path) as db:
            db.add_source(...)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to config.db_path.
        """
        self.db_path = db_path or config.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False
        self._workspace_id_verified = False  # Track if workspace ID has been verified
        self._init_db()

    def __enter__(self) -> "SQLiteManager":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, ensuring cleanup."""
        self.close()

    def close(self) -> None:
        """Close the storage and release all database resources.

        This method ensures all SQLite connections are properly closed and
        any WAL/journal files are cleaned up. Call this before deleting
        the database file, especially on Windows.
        """
        if self._closed:
            return
        self._closed = True

        # Force garbage collection to release any lingering connections
        import gc
        gc.collect()

        # Force a checkpoint and close any WAL files
        try:
            conn = sqlite3.connect(self.db_path)
            # Disable WAL mode to ensure no -wal/-shm files remain
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except sqlite3.Error:
            pass  # Database may not exist or be accessible

        # Final GC pass
        gc.collect()

    def _init_db(self) -> None:
        """Initialize database schema including FTS5 tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Workspace metadata table (M7: workspace isolation guard)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_meta (
                    workspace_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT
                )
                """
            )

            # Sources table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    uri TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

            # Add uri column if it doesn't exist (migration for existing DBs)
            try:
                cursor.execute("ALTER TABLE sources ADD COLUMN uri TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add content_hash column for deduplication (M5 migration)
            try:
                cursor.execute("ALTER TABLE sources ADD COLUMN content_hash TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add run_id column to link sources to runs (M5 migration)
            try:
                cursor.execute("ALTER TABLE sources ADD COLUMN run_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Companies table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

            # Artifacts table (tracks outputs)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    name TEXT,
                    content_json TEXT,
                    content_md TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
                """
            )

            # Add content columns if they don't exist (migration for existing DBs)
            for col in ["name", "content_json", "content_md"]:
                try:
                    cursor.execute(f"ALTER TABLE artifacts ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Claims table with normalized source_ids (JSON array)
            # kind: 'fact', 'assumption', 'inference'
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL,
                    claim_text TEXT NOT NULL,
                    kind TEXT DEFAULT 'assumption',
                    is_assumption INTEGER DEFAULT 0,
                    source_ids TEXT DEFAULT '[]',
                    confidence REAL,
                    created_at TEXT,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
                """
            )

            # Add new columns if they don't exist (migration for existing DBs)
            for col, default in [("kind", "'assumption'"), ("created_at", "NULL")]:
                try:
                    cursor.execute(
                        f"ALTER TABLE claims ADD COLUMN {col} TEXT DEFAULT {default}"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Initialize FTS5 tables
            self._init_fts5(cursor)

            conn.commit()

    def _init_fts5(self, cursor: sqlite3.Cursor) -> None:
        """Initialize FTS5 full-text search tables and triggers.

        Creates FTS5 virtual tables for sources and artifacts,
        with triggers to keep them in sync with base tables.

        Note: Using regular (non-external-content) FTS5 tables for simplicity
        and reliability. Content is duplicated but this avoids column mapping
        issues and works reliably across SQLite versions.

        Args:
            cursor: SQLite cursor to use
        """
        # FTS5 table for sources (stores content directly)
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
                source_id,
                title,
                uri,
                content
            )
            """
        )

        # FTS5 table for artifacts (stores content directly)
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
                artifact_id,
                name,
                artifact_type,
                content
            )
            """
        )

        # Triggers to keep sources_fts in sync
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS sources_ai AFTER INSERT ON sources BEGIN
                INSERT INTO sources_fts(source_id, title, uri, content)
                VALUES (NEW.id, NEW.title, NEW.uri, NEW.content);
            END
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS sources_ad AFTER DELETE ON sources BEGIN
                DELETE FROM sources_fts WHERE source_id = OLD.id;
            END
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS sources_au AFTER UPDATE ON sources BEGIN
                DELETE FROM sources_fts WHERE source_id = OLD.id;
                INSERT INTO sources_fts(source_id, title, uri, content)
                VALUES (NEW.id, NEW.title, NEW.uri, NEW.content);
            END
            """
        )

        # Triggers to keep artifacts_fts in sync
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts BEGIN
                INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
                VALUES (NEW.id, NEW.name, NEW.artifact_type,
                        COALESCE(NEW.content_md, '') || ' ' || COALESCE(NEW.content_json, ''));
            END
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts BEGIN
                DELETE FROM artifacts_fts WHERE artifact_id = OLD.id;
            END
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts BEGIN
                DELETE FROM artifacts_fts WHERE artifact_id = OLD.id;
                INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
                VALUES (NEW.id, NEW.name, NEW.artifact_type,
                        COALESCE(NEW.content_md, '') || ' ' || COALESCE(NEW.content_json, ''));
            END
            """
        )

    def rebuild_fts_index(self) -> None:
        """Rebuild FTS indexes from base tables.

        Useful after bulk imports or when FTS gets out of sync.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Rebuild sources_fts
            cursor.execute("DELETE FROM sources_fts")
            cursor.execute(
                """
                INSERT INTO sources_fts(source_id, title, uri, content)
                SELECT id, title, uri, content FROM sources
                """
            )

            # Rebuild artifacts_fts
            cursor.execute("DELETE FROM artifacts_fts")
            cursor.execute(
                """
                INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
                SELECT id, name, artifact_type,
                       COALESCE(content_md, '') || ' ' || COALESCE(content_json, '')
                FROM artifacts
                """
            )

            conn.commit()

    # ========================================================================
    # Workspace Metadata (M7: Isolation Guard)
    # ========================================================================

    def init_workspace_metadata(self, workspace_id: str) -> None:
        """Initialize workspace metadata for a new database.

        Args:
            workspace_id: Workspace ID to set

        Raises:
            ValueError: If workspace metadata already exists with different ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if metadata already exists
            cursor.execute("SELECT workspace_id FROM workspace_meta")
            row = cursor.fetchone()

            if row:
                existing_id = row[0]
                if existing_id != workspace_id:
                    raise ValueError(
                        f"Database already initialized with workspace_id {existing_id}, "
                        f"cannot reinitialize with {workspace_id}"
                    )
                # Already initialized with correct ID, just update access time
                cursor.execute(
                    "UPDATE workspace_meta SET last_accessed = ?",
                    (datetime.now(timezone.utc).isoformat(),),
                )
            else:
                # Initialize new workspace metadata
                cursor.execute(
                    """
                    INSERT INTO workspace_meta (workspace_id, created_at, last_accessed)
                    VALUES (?, ?, ?)
                    """,
                    (
                        workspace_id,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

            conn.commit()
            self._workspace_id_verified = True

    def get_workspace_id(self) -> Optional[str]:
        """Get the workspace ID from database metadata.

        Returns:
            Workspace ID if set, None if not initialized
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_id FROM workspace_meta")
            row = cursor.fetchone()
            return row[0] if row else None

    def verify_workspace_id(self, expected_workspace_id: str) -> None:
        """Verify that database workspace ID matches expected ID.

        This is a guard to prevent cross-workspace access.

        Args:
            expected_workspace_id: Expected workspace ID

        Raises:
            WorkspaceMismatchError: If workspace ID doesn't match
        """
        if self._workspace_id_verified:
            return  # Already verified

        actual_id = self.get_workspace_id()

        if actual_id is None:
            # Database not initialized, initialize it now
            self.init_workspace_metadata(expected_workspace_id)
            self._workspace_id_verified = True
            return

        if actual_id != expected_workspace_id:
            from agnetwork.workspaces import WorkspaceMismatchError

            raise WorkspaceMismatchError(expected=expected_workspace_id, actual=actual_id)

        # Update last accessed
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE workspace_meta SET last_accessed = ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

        self._workspace_id_verified = True

    # ========================================================================
    # Source Management
    # ========================================================================

    def insert_source(
        self,
        source_id: str,
        source_type: str,
        content: str,
        title: Optional[str] = None,
        uri: Optional[str] = None,
        metadata: Optional[Dict] = None,
        content_hash: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Insert a source into the database.

        Args:
            source_id: Unique identifier for the source
            source_type: Type of source (url, text, file)
            content: Source content
            title: Optional title
            uri: Optional URI/URL
            metadata: Optional metadata dict
            content_hash: Optional SHA256 hash for deduplication
            run_id: Optional run ID that captured this source
        """
        meta_str = json.dumps(metadata or {})
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sources
                (id, source_type, title, content, uri, created_at, metadata, content_hash, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    title,
                    content,
                    uri,
                    datetime.now(timezone.utc).isoformat(),
                    meta_str,
                    content_hash,
                    run_id,
                ),
            )
            conn.commit()

    def upsert_source_from_capture(
        self,
        source_id: str,
        url: str,
        final_url: str,
        title: Optional[str],
        clean_text: str,
        content_hash: str,
        fetched_at: str,
        run_id: Optional[str] = None,
    ) -> bool:
        """Upsert a source from web capture.

        Uses content_hash for deduplication. If a source with the same
        hash already exists, it's updated with the new run_id linkage.

        Args:
            source_id: Unique identifier for the source
            url: Original URL
            final_url: Final URL after redirects
            title: Page title
            clean_text: Extracted clean text
            content_hash: SHA256 hash of content
            fetched_at: ISO timestamp of fetch
            run_id: Run ID that captured this source

        Returns:
            True if inserted/updated, False if dedupe match found
        """
        metadata = {
            "original_url": url,
            "fetched_at": fetched_at,
        }
        meta_str = json.dumps(metadata)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check for existing source with same hash
            cursor.execute(
                "SELECT id FROM sources WHERE content_hash = ?",
                (content_hash,),
            )
            existing = cursor.fetchone()

            if existing:
                # Update run_id linkage if different source
                if existing[0] != source_id:
                    return False  # Dedupe: same content already exists

            # Insert or replace
            cursor.execute(
                """
                INSERT OR REPLACE INTO sources
                (id, source_type, title, content, uri, created_at, metadata, content_hash, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    "url",
                    title,
                    clean_text,
                    final_url,
                    datetime.now(timezone.utc).isoformat(),
                    meta_str,
                    content_hash,
                    run_id,
                ),
            )
            conn.commit()
            return True

    def get_source_by_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get a source by content hash.

        Args:
            content_hash: SHA256 hash to look up

        Returns:
            Source dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE content_hash = ?", (content_hash,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get a source by ID.

        Args:
            source_id: Source ID to retrieve

        Returns:
            Source dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_sources(self, company: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve sources, optionally filtered by company.

        Args:
            company: Optional company name to filter by

        Returns:
            List of source dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if company:
                cursor.execute(
                    "SELECT * FROM sources WHERE metadata LIKE ?",
                    (f"%{company}%",),
                )
            else:
                cursor.execute("SELECT * FROM sources")
            return [dict(row) for row in cursor.fetchall()]

    def insert_company(self, company_id: str, name: str) -> None:
        """Insert a company into the database.

        Args:
            company_id: Unique company ID
            name: Company name
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO companies (id, name, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (company_id, name, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Company already exists
                pass

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get a company by ID.

        Args:
            company_id: Company ID to retrieve

        Returns:
            Company dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a company by name.

        Args:
            name: Company name to retrieve

        Returns:
            Company dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def insert_artifact(
        self,
        artifact_id: str,
        company_id: str,
        artifact_type: str,
        run_id: str,
        name: Optional[str] = None,
        content_json: Optional[str] = None,
        content_md: Optional[str] = None,
    ) -> None:
        """Insert an artifact into the database.

        Args:
            artifact_id: Unique artifact ID
            company_id: Associated company ID
            artifact_type: Type of artifact (research_brief, target_map, etc.)
            run_id: Run ID that generated this artifact
            name: Artifact name
            content_json: JSON content string
            content_md: Markdown content string
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO artifacts
                (id, company_id, artifact_type, run_id, name, content_json, content_md, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    company_id,
                    artifact_type,
                    run_id,
                    name,
                    content_json,
                    content_md,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get an artifact by ID.

        Args:
            artifact_id: Artifact ID to retrieve

        Returns:
            Artifact dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_artifacts_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all artifacts for a run.

        Args:
            run_id: Run ID to filter by

        Returns:
            List of artifact dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def insert_claim(
        self,
        claim_id: str,
        artifact_id: str,
        claim_text: str,
        kind: str = "assumption",
        source_ids: Optional[List[str]] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """Insert a claim into the database.

        Args:
            claim_id: Unique claim ID
            artifact_id: Associated artifact ID
            claim_text: The claim text
            kind: Claim kind (fact, assumption, inference)
            source_ids: List of source IDs (stored as JSON array)
            confidence: Confidence score 0.0-1.0
        """
        # Always serialize as JSON array (canonical format)
        source_ids_json = serialize_source_ids(source_ids)
        is_assumption = 1 if kind in ("assumption", "inference") else 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO claims
                (id, artifact_id, claim_text, kind, is_assumption, source_ids, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    artifact_id,
                    claim_text,
                    kind,
                    is_assumption,
                    source_ids_json,
                    confidence,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get a claim by ID with normalized source_ids.

        Args:
            claim_id: Claim ID to retrieve

        Returns:
            Claim dict with source_ids as list, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Normalize source_ids to list
                result["source_ids"] = normalize_source_ids(result.get("source_ids"))
                return result
            return None

    def get_claims_by_artifact(self, artifact_id: str) -> List[Dict[str, Any]]:
        """Get all claims for an artifact.

        Args:
            artifact_id: Artifact ID to filter by

        Returns:
            List of claim dicts with normalized source_ids
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM claims WHERE artifact_id = ?", (artifact_id,)
            )
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result["source_ids"] = normalize_source_ids(result.get("source_ids"))
                results.append(result)
            return results

    def source_exists(self, source_id: str) -> bool:
        """Check if a source exists.

        Args:
            source_id: Source ID to check

        Returns:
            True if source exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM sources WHERE id = ? LIMIT 1", (source_id,)
            )
            return cursor.fetchone() is not None

    def artifact_exists(self, artifact_id: str) -> bool:
        """Check if an artifact exists.

        Args:
            artifact_id: Artifact ID to check

        Returns:
            True if artifact exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM artifacts WHERE id = ? LIMIT 1", (artifact_id,)
            )
            return cursor.fetchone() is not None

    # ===========================================
    # FTS5 Search Methods (M4 Memory Retrieval)
    # ===========================================

    def search_sources_fts(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search sources using FTS5 full-text search.

        Args:
            query: Search query (FTS5 query syntax supported)
            limit: Maximum number of results

        Returns:
            List of source hits with id, title, excerpt, score, and metadata
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Use FTS5 MATCH with BM25 ranking
            # Join using source_id column stored in FTS table
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.source_type,
                    s.title,
                    s.uri,
                    s.created_at,
                    s.metadata,
                    snippet(sources_fts, 3, '<mark>', '</mark>', '...', 32) as excerpt,
                    bm25(sources_fts) as score
                FROM sources_fts
                JOIN sources s ON sources_fts.source_id = s.id
                WHERE sources_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit),
            )

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # Parse metadata JSON
                if result.get("metadata"):
                    try:
                        result["metadata"] = json.loads(result["metadata"])
                    except json.JSONDecodeError:
                        result["metadata"] = {}
                else:
                    result["metadata"] = {}
                results.append(result)

            return results

    def search_artifacts_fts(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search artifacts using FTS5 full-text search.

        Args:
            query: Search query (FTS5 query syntax supported)
            limit: Maximum number of results

        Returns:
            List of artifact hits with id, name, type, excerpt, and score
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Use FTS5 MATCH with BM25 ranking
            # Join using artifact_id column stored in FTS table
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.company_id,
                    a.artifact_type,
                    a.run_id,
                    a.name,
                    a.created_at,
                    snippet(artifacts_fts, 3, '<mark>', '</mark>', '...', 32) as excerpt,
                    bm25(artifacts_fts) as score
                FROM artifacts_fts
                JOIN artifacts a ON artifacts_fts.artifact_id = a.id
                WHERE artifacts_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_all_sources(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all sources, ordered by creation date.

        Args:
            limit: Maximum number of results

        Returns:
            List of source dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sources ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get("metadata"):
                    try:
                        result["metadata"] = json.loads(result["metadata"])
                    except json.JSONDecodeError:
                        result["metadata"] = {}
                results.append(result)
            return results

    def get_all_artifacts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all artifacts, ordered by creation date.

        Args:
            limit: Maximum number of results

        Returns:
            List of artifact dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
