"""
ORION Investigation Store

Lightweight SQLite persistence for investigation history.

This module deliberately stores structured investigation data rather
than relying on generated prose.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "orion_history.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            question TEXT NOT NULL,
            intent TEXT,
            status TEXT,
            result_json TEXT NOT NULL
        )
        """
    )

    connection.commit()
    return connection


def create_investigation_id() -> str:
    """
    Create a short human-readable investigation ID.
    """
    return f"INV-{uuid.uuid4().hex[:10].upper()}"


def save_investigation(
    question: str,
    result: Dict[str, Any],
    investigation_id: Optional[str] = None,
) -> str:
    """
    Persist a structured investigation result.

    Returns the investigation ID.
    """

    investigation_id = investigation_id or create_investigation_id()

    intent = result.get("intent")
    status = result.get("status")

    connection = _connect()

    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO investigations
            (
                id,
                created_at,
                question,
                intent,
                status,
                result_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                investigation_id,
                _utc_now(),
                question,
                intent,
                status,
                json.dumps(result, ensure_ascii=False, default=str),
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return investigation_id


def get_investigation(
    investigation_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve one investigation.
    """

    connection = _connect()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM investigations
            WHERE id = ?
            """,
            (investigation_id,),
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        return None

    result = json.loads(row["result_json"])

    result["investigation_id"] = row["id"]
    result["created_at"] = row["created_at"]

    return result


def list_investigations(
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return recent investigations.
    """

    limit = max(1, min(int(limit), 100))

    connection = _connect()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                question,
                intent,
                status
            FROM investigations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    finally:
        connection.close()

    return [
        {
            "investigation_id": row["id"],
            "created_at": row["created_at"],
            "question": row["question"],
            "intent": row["intent"],
            "status": row["status"],
        }
        for row in rows
    ]