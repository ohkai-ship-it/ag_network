"""SQLite database operations for BD Copilot."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bdcopilot.config import config


class SQLiteManager:
    """Manages SQLite database for entities and traceability."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        self.db_path = db_path or config.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Sources table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

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
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
                """
            )

            # Traceability table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL,
                    claim_text TEXT NOT NULL,
                    is_assumption INTEGER DEFAULT 0,
                    source_ids TEXT,
                    confidence REAL,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
                """
            )

            conn.commit()

    def insert_source(
        self,
        source_id: str,
        source_type: str,
        content: str,
        title: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Insert a source into the database."""
        import json

        meta_str = json.dumps(metadata or {})
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sources
                (id, source_type, title, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    title,
                    content,
                    datetime.utcnow().isoformat(),
                    meta_str,
                ),
            )
            conn.commit()

    def get_sources(self, company: str) -> List[Dict[str, Any]]:
        """Retrieve sources related to a company."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sources WHERE metadata LIKE ?",
                (f"%{company}%",),
            )
            return [dict(row) for row in cursor.fetchall()]

    def insert_company(self, company_id: str, name: str) -> None:
        """Insert a company into the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO companies (id, name, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (company_id, name, datetime.utcnow().isoformat()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Company already exists
                pass
