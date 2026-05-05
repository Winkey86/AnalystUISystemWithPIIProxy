from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger("analyst-mcp.audit")


def _ensure_path() -> Path:
    p = Path(settings.audit_log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def log_tool_call(
    tool_name: str,
    args_keys: list[str],
    result_type: str,
    elapsed_ms: float,
    error: str | None = None,
) -> None:
    if not settings.audit_enabled:
        return
    record: dict[str, Any] = {
        "ts": time.time(),
        "tool": tool_name,
        "args_keys": args_keys,
        "result_type": result_type,
        "elapsed_ms": round(elapsed_ms, 1),
    }
    if error:
        record["error"] = error
    try:
        with _ensure_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to write audit log")


def read_audit_log(limit: int = 100) -> list[dict[str, Any]]:
    p = Path(settings.audit_log_path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    records = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(records) >= limit:
            break
    return records
