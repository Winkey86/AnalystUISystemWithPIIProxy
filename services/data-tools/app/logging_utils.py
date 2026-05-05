from datetime import datetime, timezone
from typing import Optional
import json
import uuid

from app.artifact_store import ensure_dirs
from app.config import Settings, get_settings
from app.contracts import ToolCallLog


def request_id_or_new(request_id: Optional[str]) -> str:
    return request_id or str(uuid.uuid4())


def log_tool_call(
    tool_name: str,
    request_id: str,
    status: str,
    latency_ms: int,
    dataset_id: Optional[str] = None,
    error: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> None:
    settings = settings or get_settings()
    ensure_dirs(settings)
    log = ToolCallLog(
        timestamp=datetime.now(timezone.utc).isoformat(),
        request_id=request_id,
        tool_name=tool_name,
        dataset_id=dataset_id,
        status=status,
        latency_ms=latency_ms,
        error=error,
    )
    payload = _model_dump(log)
    log_path = settings.artifact_root / "logs" / "tool_calls.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
