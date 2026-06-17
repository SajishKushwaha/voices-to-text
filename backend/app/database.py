import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .config import Settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def init_database(settings: Settings) -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS transcripts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              language TEXT,
              duration_seconds REAL,
              source TEXT NOT NULL DEFAULT 'voice_to_text',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pdf_reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              original_filename TEXT NOT NULL,
              stored_path TEXT NOT NULL,
              extracted_text TEXT NOT NULL,
              extracted_data TEXT NOT NULL,
              confidence REAL NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              report_id INTEGER NOT NULL,
              reviewed_data TEXT NOT NULL,
              reviewer TEXT NOT NULL,
              notes TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(report_id) REFERENCES pdf_reports(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              entity_type TEXT NOT NULL,
              entity_id INTEGER,
              action TEXT NOT NULL,
              metadata TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )


@contextmanager
def get_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def insert_audit_log(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: int | None,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (entity_type, entity_id, action, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_id,
            action,
            json_dumps(metadata or {}),
            utc_now(),
        ),
    )
