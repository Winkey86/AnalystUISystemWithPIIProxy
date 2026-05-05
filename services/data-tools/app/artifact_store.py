from pathlib import Path
from typing import Optional
import re

import pandas as pd

from app.config import Settings, get_settings
from app.contracts import ToolError


SAFE_ID_RE = re.compile(r"^[a-z0-9_-]+$")


def validate_safe_id(value: str, label: str = "id") -> str:
    if not value or not SAFE_ID_RE.fullmatch(value):
        raise ToolError(
            f"{label} must contain only lowercase latin letters, digits, underscore or hyphen",
            status_code=400,
            code="invalid_id",
        )
    return value


def ensure_dirs(settings: Optional[Settings] = None) -> None:
    settings = settings or get_settings()
    for rel in ("datasets", "query_results", "metadata", "logs"):
        (settings.artifact_root / rel).mkdir(parents=True, exist_ok=True)


def dataset_path(dataset_id: str, settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    validate_safe_id(dataset_id, "dataset_id")
    return settings.artifact_root / "datasets" / f"{dataset_id}.parquet"


def query_result_path(query_id: str, settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    validate_safe_id(query_id, "query_id")
    return settings.artifact_root / "query_results" / f"{query_id}.parquet"


def save_dataset(df: pd.DataFrame, dataset_id: str, settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    ensure_dirs(settings)
    path = dataset_path(dataset_id, settings)
    df.to_parquet(path, index=False)
    return f"artifact://datasets/{dataset_id}.parquet"


def load_dataset(dataset_id: str, settings: Optional[Settings] = None) -> pd.DataFrame:
    settings = settings or get_settings()
    path = dataset_path(dataset_id, settings)
    if not path.exists():
        raise ToolError(f"Dataset artifact not found: {dataset_id}", status_code=404, code="dataset_not_found")
    return pd.read_parquet(path)


def save_query_result(df: pd.DataFrame, query_id: str, settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    ensure_dirs(settings)
    path = query_result_path(query_id, settings)
    df.to_parquet(path, index=False)
    return f"artifact://query_results/{query_id}.parquet"


def resolve_artifact_uri(uri: str, settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    if uri.startswith("artifact://datasets/"):
        name = uri.removeprefix("artifact://datasets/")
        if not name.endswith(".parquet"):
            raise ToolError("Dataset artifact URI must point to a parquet file", code="invalid_artifact_uri")
        return dataset_path(name[: -len(".parquet")], settings)
    if uri.startswith("artifact://query_results/"):
        name = uri.removeprefix("artifact://query_results/")
        if not name.endswith(".parquet"):
            raise ToolError("Query artifact URI must point to a parquet file", code="invalid_artifact_uri")
        return query_result_path(name[: -len(".parquet")], settings)
    raise ToolError(f"Unsupported artifact URI: {uri}", status_code=400, code="invalid_artifact_uri")
