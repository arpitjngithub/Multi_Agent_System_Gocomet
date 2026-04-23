from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "pipeline.db"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              document_id TEXT UNIQUE,
              filename TEXT,
              uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              extraction_result TEXT,
              validation_result TEXT,
              router_decision TEXT,
              router_reasoning TEXT,
              router_payload TEXT,
              pipeline_status TEXT,
              current_stage TEXT,
              error_message TEXT,
              completed_at TIMESTAMP
            );
            """
        )
        conn.commit()


def create_run(document_id: str, filename: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs (
              document_id, filename, pipeline_status, current_stage
            ) VALUES (?, ?, ?, ?)
            """,
            (document_id, filename, "running", "queued"),
        )
        conn.commit()


def update_run(
    document_id: str,
    *,
    extraction_result: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
    router_decision: str | None = None,
    router_reasoning: str | None = None,
    router_payload: dict[str, Any] | None = None,
    pipeline_status: str | None = None,
    current_stage: str | None = None,
    error_message: str | None = None,
    completed_at: datetime | None = None,
) -> None:
    fields: list[str] = []
    values: list[Any] = []

    if extraction_result is not None:
        fields.append("extraction_result = ?")
        values.append(json.dumps(extraction_result))
    if validation_result is not None:
        fields.append("validation_result = ?")
        values.append(json.dumps(validation_result))
    if router_decision is not None:
        fields.append("router_decision = ?")
        values.append(router_decision)
    if router_reasoning is not None:
        fields.append("router_reasoning = ?")
        values.append(router_reasoning)
    if router_payload is not None:
        fields.append("router_payload = ?")
        values.append(json.dumps(router_payload))
    if pipeline_status is not None:
        fields.append("pipeline_status = ?")
        values.append(pipeline_status)
    if current_stage is not None:
        fields.append("current_stage = ?")
        values.append(current_stage)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if completed_at is not None:
        fields.append("completed_at = ?")
        values.append(completed_at.isoformat())

    if not fields:
        return

    values.append(document_id)
    query = f"UPDATE pipeline_runs SET {', '.join(fields)} WHERE document_id = ?"
    with get_connection() as conn:
        conn.execute(query, values)
        conn.commit()


def get_run(document_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE document_id = ?",
            (document_id,),
        ).fetchone()
    return normalize_row(row) if row else None


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY uploaded_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [normalize_row(row) for row in rows]


def run_sql(query: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def get_schema_description() -> str:
    return """
Table: pipeline_runs
- id INTEGER PRIMARY KEY AUTOINCREMENT
- document_id TEXT UNIQUE
- filename TEXT
- uploaded_at TIMESTAMP
- extraction_result TEXT (JSON)
- validation_result TEXT (JSON)
- router_decision TEXT
- router_reasoning TEXT
- router_payload TEXT (JSON)
- pipeline_status TEXT
- current_stage TEXT
- error_message TEXT
- completed_at TIMESTAMP
"""


def normalize_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    for key in ("extraction_result", "validation_result", "router_payload"):
        value = payload.get(key)
        if value:
            payload[key] = json.loads(value)
    return payload
