from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS request_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  request_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  route TEXT NOT NULL,
  model_alias TEXT NOT NULL,
  stream INTEGER NOT NULL,
  status INTEGER,
  latency_ms REAL,
  incoming_json TEXT,
  upstream_json TEXT,
  response_json TEXT,
  error TEXT,
  content_logged INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_request_logs_ts ON request_logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_request_logs_request_id ON request_logs(request_id);
"""


def _connect() -> sqlite3.Connection:
    Path(settings.audit_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.audit_db_path)
    conn.executescript(SCHEMA)
    return conn


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in {"authorization", "api_key", "token", "secret", "password"}:
                redacted[key] = "[REDACTED]"
            elif lowered == "content":
                redacted[key] = "[REDACTED_CONTENT]"
            elif lowered == "stream_sample":
                redacted[key] = "[REDACTED_STREAM_SAMPLE]"
            elif key == "messages" and isinstance(item, list):
                redacted[key] = [_redact_message(message) for message in item]
            else:
                redacted[key] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_message(message: Any) -> Any:
    if not isinstance(message, dict):
        return "[REDACTED_MESSAGE]"
    safe = dict(message)
    if "content" in safe:
        safe["content"] = "[REDACTED_CONTENT]"
    return _redact_value(safe)


def _dump(value: Any, *, allow_content: bool) -> str | None:
    if value is None:
        return None
    payload = value if allow_content else _redact_value(value)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _insert_sync(record: dict[str, Any]) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO request_logs (
              ts, request_id, provider, route, model_alias, stream, status,
              latency_ms, incoming_json, upstream_json, response_json, error,
              content_logged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                record["request_id"],
                record["provider"],
                record["route"],
                record["model_alias"],
                1 if record["stream"] else 0,
                record.get("status"),
                record.get("latency_ms"),
                _dump(record.get("incoming_json"), allow_content=record["content_logged"]),
                _dump(record.get("upstream_json"), allow_content=record["content_logged"]),
                _dump(record.get("response_json"), allow_content=record["content_logged"]),
                record.get("error"),
                1 if record["content_logged"] else 0,
            ),
        )
        conn.execute(
            """
            DELETE FROM request_logs
            WHERE id NOT IN (
              SELECT id FROM request_logs ORDER BY ts DESC LIMIT ?
            )
            """,
            (settings.audit_retention,),
        )
        return int(cursor.lastrowid)


async def insert_request_log(
    *,
    request_id: str,
    provider: str,
    route: str,
    model_alias: str,
    stream: bool,
    status: int | None,
    latency_ms: float | None,
    incoming_json: Any = None,
    upstream_json: Any = None,
    response_json: Any = None,
    error: str | None = None,
) -> int:
    return await asyncio.to_thread(
        _insert_sync,
        {
            "request_id": request_id,
            "provider": provider,
            "route": route,
            "model_alias": model_alias,
            "stream": stream,
            "status": status,
            "latency_ms": latency_ms,
            "incoming_json": incoming_json,
            "upstream_json": upstream_json,
            "response_json": response_json,
            "error": error,
            "content_logged": settings.audit_log_content,
        },
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for field in ("incoming_json", "upstream_json", "response_json"):
        if result[field]:
            try:
                result[field] = json.loads(result[field])
            except json.JSONDecodeError:
                pass
    result["stream"] = bool(result["stream"])
    result["content_logged"] = bool(result["content_logged"])
    return result


def _list_sync(limit: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM request_logs ORDER BY ts DESC LIMIT ?",
            (min(max(limit, 1), settings.audit_retention),),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]


async def list_request_logs(limit: int = 100) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_sync, limit)
