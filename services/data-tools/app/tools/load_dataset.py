from pathlib import Path
from typing import Callable, Dict, Tuple
import re
import uuid

import pandas as pd

from app.artifact_store import dataset_path, save_dataset, validate_safe_id
from app.config import get_settings
from app.contracts import DatasetMetadata, LoadDatasetRequest, LoadDatasetResponse, SchemaSummary, ToolError
from app.metadata_registry import MetadataRegistry, utc_now_iso
from app.readers.csv_reader import read_csv_dataset
from app.readers.excel_reader import read_excel_dataset
from app.readers.json_reader import read_json_dataset
from app.readers.parquet_reader import read_parquet_dataset
from app.security.pii_column_detector import detect_pii_columns
from app.tools.common import normalize_columns


Reader = Callable[[Path, Dict], Tuple[pd.DataFrame, list]]

READERS: Dict[str, Reader] = {
    "csv": read_csv_dataset,
    "xlsx": read_excel_dataset,
    "json": read_json_dataset,
    "parquet": read_parquet_dataset,
}


def load_dataset_tool(request: LoadDatasetRequest) -> LoadDatasetResponse:
    settings = get_settings()
    if request.source_type != "file":
        raise ToolError("Only source_type='file' is supported", status_code=400, code="unsupported_source_type")

    source_format = request.format.lower().lstrip(".")
    reader = READERS.get(source_format)
    if reader is None:
        raise ToolError(
            f"Unsupported dataset format: {request.format}. Supported formats: csv, xlsx, json, parquet",
            status_code=400,
            code="unsupported_format",
        )

    source_path = resolve_input_path(request.path)
    _check_file_size(source_path)

    dataset_id = make_dataset_id(request.dataset_name, source_path)
    validate_safe_id(dataset_id, "dataset_id")

    registry = MetadataRegistry(settings)
    if registry.exists(dataset_id) and not request.overwrite:
        raise ToolError(
            f"Dataset already exists: {dataset_id}. Use overwrite=true to replace it.",
            status_code=409,
            code="dataset_exists",
        )

    try:
        df, warnings = reader(source_path, request.options)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(
            f"Failed to read {source_format} dataset: {exc}",
            status_code=400,
            code="dataset_read_failed",
        ) from exc
    df = normalize_columns(df)
    artifact_uri = save_dataset(df, dataset_id, settings)
    local_path = dataset_path(dataset_id, settings)
    pii_columns = detect_pii_columns(df.columns)

    metadata = DatasetMetadata(
        dataset_id=dataset_id,
        artifact_uri=artifact_uri,
        local_path=str(local_path),
        rows=int(len(df)),
        columns=int(len(df.columns)),
        dtypes={str(column): str(dtype) for column, dtype in df.dtypes.items()},
        created_at=utc_now_iso(),
        source_path=str(source_path),
        source_format=source_format,
        pii_columns=pii_columns,
    )
    registry.upsert(metadata, overwrite=request.overwrite)

    return LoadDatasetResponse(
        status="ok",
        dataset_id=dataset_id,
        artifact_uri=artifact_uri,
        schema_summary=SchemaSummary(rows=len(df), columns=len(df.columns)),
        warnings=warnings,
    )


def resolve_input_path(raw_path: str) -> Path:
    settings = get_settings()
    input_root = settings.data_input_dir.resolve()
    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (input_root / candidate).resolve()

    try:
        resolved.relative_to(input_root)
    except ValueError as exc:
        raise ToolError(
            f"File path must stay inside DATA_INPUT_DIR: {input_root}",
            status_code=400,
            code="path_outside_input_dir",
        ) from exc

    if not resolved.exists() or not resolved.is_file():
        raise ToolError(f"Input file not found: {raw_path}", status_code=404, code="input_file_not_found")
    return resolved


def _check_file_size(path: Path) -> None:
    settings = get_settings()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    size = path.stat().st_size
    if size > max_bytes:
        raise ToolError(
            f"File is too large: {size} bytes. MAX_FILE_SIZE_MB={settings.max_file_size_mb}",
            status_code=413,
            code="file_too_large",
        )


def make_dataset_id(dataset_name: str | None, source_path: Path) -> str:
    base = dataset_name or f"{source_path.stem}-{uuid.uuid4().hex[:8]}"
    slug = re.sub(r"[^a-z0-9_-]+", "-", base.lower()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = f"dataset-{uuid.uuid4().hex[:8]}"
    return slug
