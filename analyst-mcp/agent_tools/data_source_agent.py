from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx
import pandas as pd

from config import settings
from direct_tools.artifacts import load_dataframe, save_dataframe


def _uploads_dir() -> Path:
    d = Path(settings.uploads_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_path(base: Path, name: str) -> Path:
    p = (base / name).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise ValueError("Path traversal not allowed")
    return p


def _save_metadata(dataset_id: str, meta: dict) -> None:
    d = Path(settings.metadata_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dataset_id}.json"
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def data_source_agent(
        source_type: str,
        path_or_url: str,
        options: dict | None = None,
        anonymize: bool = False,
    ) -> dict[str, Any]:
        """Загрузить данные из источника и сохранить как артефакт.

        Args:
            source_type: Тип источника: 'csv', 'excel', 'json', 'parquet',
                         'sqlite', 'postgres', 'api'.
            path_or_url: Путь к файлу (в /data/uploads/) или URL.
            options: Дополнительные параметры:
                     - sheet (str): для excel — имя листа
                     - separator (str): для csv — разделитель
                     - table (str): для sqlite/postgres — имя таблицы
                     - query (str): для sqlite/postgres — SQL SELECT
                     - nrows (int): ограничение строк
            anonymize: Если True — передать данные через anon-proxy после загрузки.

        Returns:
            {
                "status": "ok" | "error",
                "dataset_id": str,
                "artifact_id": str,
                "artifacts": list[str],
                "schema_summary": {"rows": int, "columns": int},
                "error": str  # только при ошибке
            }
        """
        opts = options or {}
        nrows = opts.get("nrows", settings.max_rows_load)

        try:
            df = _load(source_type, path_or_url, opts, nrows)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        dataset_id = f"ds_{Path(path_or_url).stem}_{uuid.uuid4().hex[:6]}"
        artifact_id = save_dataframe(df, dataset_id)

        meta = {
            "dataset_id": dataset_id,
            "artifact_id": artifact_id,
            "source_type": source_type,
            "source": path_or_url,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        }
        _save_metadata(dataset_id, meta)

        result: dict[str, Any] = {
            "status": "ok",
            "dataset_id": dataset_id,
            "artifact_id": artifact_id,
            "artifacts": [f"artifact://{artifact_id}"],
            "schema_summary": {"rows": len(df), "columns": len(df.columns)},
        }

        if anonymize:
            anon_result = _anonymize(df, dataset_id)
            result["anonymized_artifact_id"] = anon_result.get("artifact_id")
            result["anonymize_status"] = anon_result.get("status")

        return result


def _load(source_type: str, path_or_url: str, opts: dict, nrows: int) -> pd.DataFrame:
    if source_type == "csv":
        p = _safe_path(_uploads_dir(), path_or_url)
        sep = opts.get("separator", ",")
        return pd.read_csv(p, nrows=nrows, sep=sep)

    if source_type == "excel":
        p = _safe_path(_uploads_dir(), path_or_url)
        sheet = opts.get("sheet", 0)
        return pd.read_excel(p, sheet_name=sheet, nrows=nrows, engine="openpyxl")

    if source_type == "json":
        p = _safe_path(_uploads_dir(), path_or_url)
        raw = json.loads(p.read_text(encoding="utf-8"))
        df = pd.DataFrame(raw) if isinstance(raw, list) else pd.json_normalize(raw)
        return df.head(nrows)

    if source_type == "parquet":
        p = _safe_path(_uploads_dir(), path_or_url)
        return pd.read_parquet(p).head(nrows)

    if source_type == "sqlite":
        import sqlite3

        db_path = _safe_path(_uploads_dir(), path_or_url)
        query = opts.get("query") or f"SELECT * FROM {opts['table']} LIMIT {nrows}"
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(query, conn)

    if source_type == "postgres":
        from sqlalchemy import create_engine, text

        url = path_or_url  # ожидается полный DSN
        engine = create_engine(url)
        query = opts.get("query") or f"SELECT * FROM {opts['table']} LIMIT {nrows}"
        with engine.connect() as conn:
            return pd.read_sql_query(text(query), conn)

    if source_type == "api":
        resp = httpx.get(path_or_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data) if isinstance(data, list) else pd.json_normalize(data)
        return df.head(nrows)

    raise ValueError(f"Unsupported source_type: {source_type!r}")


def _anonymize(df: pd.DataFrame, dataset_id: str) -> dict[str, Any]:
    """Отправить датасет в anon-proxy, вернуть замаскированный артефакт."""
    try:
        rows = df.head(settings.max_rows_load).to_dict(orient="records")
        resp = httpx.post(
            f"{settings.anon_proxy_url}/anonymize",
            json={"dataset_id": dataset_id, "rows": rows},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        masked_rows = data.get("rows", rows)
        masked_df = pd.DataFrame(masked_rows)
        artifact_id = save_dataframe(masked_df, f"{dataset_id}_anon")
        return {"status": "ok", "artifact_id": artifact_id}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
