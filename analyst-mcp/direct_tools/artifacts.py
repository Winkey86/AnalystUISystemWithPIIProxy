from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import settings


def _safe_path(base: Path, name: str) -> Path:
    p = (base / name).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise ValueError("Path traversal not allowed")
    return p


def _artifacts_dir() -> Path:
    d = Path(settings.artifacts_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_artifact(artifact_id: str, data: list[dict] | dict, fmt: str) -> Path:
    d = _artifacts_dir()
    if fmt == "parquet":
        p = _safe_path(d, f"{artifact_id}.parquet")
        rows = data if isinstance(data, list) else [data]
        df = pd.DataFrame(rows)
        df.to_parquet(p, index=False)
    else:
        p = _safe_path(d, f"{artifact_id}.json")
        p.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    return p


def load_dataframe(artifact_id: str) -> pd.DataFrame:
    """Вспомогательная функция для agent_tools: загружает артефакт как DataFrame."""
    d = _artifacts_dir()
    parquet_p = _safe_path(d, f"{artifact_id}.parquet")
    json_p = _safe_path(d, f"{artifact_id}.json")
    if parquet_p.exists():
        return pd.read_parquet(parquet_p)
    if json_p.exists():
        raw = json.loads(json_p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        return pd.DataFrame([raw])
    raise FileNotFoundError(f"Artifact not found: {artifact_id}")


def save_dataframe(df: pd.DataFrame, name: str) -> str:
    """Вспомогательная функция для agent_tools: сохраняет DataFrame как артефакт."""
    artifact_id = f"{name}_{uuid.uuid4().hex[:8]}"
    _write_artifact(artifact_id, df.to_dict(orient="records"), "parquet")
    return artifact_id


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def artifact_list() -> dict[str, Any]:
        """Список всех сохранённых artifact_id."""
        d = _artifacts_dir()
        ids = [p.stem for p in sorted(d.iterdir()) if p.suffix in (".parquet", ".json")]
        return {"artifact_ids": ids}

    @mcp.tool()
    @audited
    def artifact_store(data: list[dict] | dict, name: str, format: str = "parquet") -> dict[str, Any]:
        """Сохранить данные как именованный артефакт.

        Args:
            data: Список строк (list[dict]) или словарь для tabular данных.
            name: Базовое имя (буквы, цифры, подчёркивание, дефис).
            format: 'parquet' (по умолчанию) или 'json'.

        Returns:
            {"artifact_id": str}
        """
        if not name or not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError("name must contain only alphanumeric characters, underscores, and hyphens")
        if format not in ("parquet", "json"):
            raise ValueError("format must be 'parquet' or 'json'")
        artifact_id = f"{name}_{uuid.uuid4().hex[:8]}"
        _write_artifact(artifact_id, data, format)
        return {"artifact_id": artifact_id}

    @mcp.tool()
    @audited
    def artifact_load(artifact_id: str) -> dict[str, Any]:
        """Загрузить артефакт по artifact_id.

        Returns:
            {"rows": list[dict], "row_count": int, "columns": list[str]}
        """
        df = load_dataframe(artifact_id)
        n = min(len(df), settings.max_rows_result)
        return {
            "rows": df.head(n).to_dict(orient="records"),
            "row_count": len(df),
            "columns": list(df.columns),
        }

    @mcp.tool()
    @audited
    def artifact_delete(artifact_id: str) -> dict[str, Any]:
        """Удалить артефакт по artifact_id."""
        d = _artifacts_dir()
        deleted = False
        for ext in (".parquet", ".json"):
            p = _safe_path(d, f"{artifact_id}{ext}")
            if p.exists():
                p.unlink()
                deleted = True
        return {"deleted": deleted, "artifact_id": artifact_id}
