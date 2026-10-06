"""
ORION Findings Store

Persists automatic findings produced by the background watcher.
Findings are like alerts, but they carry the full investigation result.
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
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            severity TEXT NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            investigation_id TEXT,
            result_json TEXT
        )
        """
    )

    connection.commit()
    return connection


def create_finding_id() -> str:
    return f"FND-{uuid.uuid4().hex[:10].upper()}"


def save_finding(
    severity: str,
    kind: str,
    title: str,
    summary: str,
    investigation_id: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> str:
    finding_id = create_finding_id()

    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO findings
            (id, created_at, severity, kind, title, summary, investigation_id, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding_id,
                _utc_now(),
                severity,
                kind,
                title,
                summary,
                investigation_id,
                json.dumps(result, ensure_ascii=False, default=str) if result else None,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return finding_id


def list_findings(limit: int = 10) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 100))

    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM findings
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        connection.close()

    findings = []
    for row in rows:
        item = {
            "finding_id": row["id"],
            "created_at": row["created_at"],
            "severity": row["severity"],
            "kind": row["kind"],
            "title": row["title"],
            "summary": row["summary"],
            "investigation_id": row["investigation_id"],
        }
        findings.append(item)

    return findings


def get_latest_finding_for_kind(kind: str) -> Optional[Dict[str, Any]]:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM findings
            WHERE kind = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (kind,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return {
        "finding_id": row["id"],
        "created_at": row["created_at"],
        "severity": row["severity"],
        "kind": row["kind"],
    }


def clear_findings() -> int:
    connection = _connect()
    try:
        cursor = connection.execute("DELETE FROM findings")
        count = cursor.rowcount
        connection.commit()
    finally:
        connection.close()

    return count