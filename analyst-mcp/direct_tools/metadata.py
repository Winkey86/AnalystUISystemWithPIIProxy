from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from config import settings


def _safe_path(base: Path, name: str) -> Path:
    p = (base / name).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise ValueError("Path traversal not allowed")
    return p


def _meta_dir() -> Path:
    d = Path(settings.metadata_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def metadata_list() -> dict[str, Any]:
        """Список dataset_id для которых есть сохранённые метаданные."""
        d = _meta_dir()
        ids = [p.stem for p in sorted(d.glob("*.json"))]
        return {"dataset_ids": ids}

    @mcp.tool()
    @audited
    def metadata_lookup(dataset_id: str) -> dict[str, Any]:
        """Описание датасета: схема, словарь колонок, единицы измерений.

        Args:
            dataset_id: Идентификатор датасета (без расширения).
        """
        d = _meta_dir()
        p = _safe_path(d, f"{dataset_id}.json")
        if not p.exists():
            return {"error": f"Metadata not found for dataset_id='{dataset_id}'"}
        return json.loads(p.read_text(encoding="utf-8"))
