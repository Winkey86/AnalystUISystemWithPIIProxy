from app.artifact_store import load_dataset
from app.config import get_settings
from app.contracts import PreviewDatasetRequest, PreviewDatasetResponse, ToolError
from app.metadata_registry import MetadataRegistry
from app.security.pii_column_detector import detect_pii_columns, mask_records
from app.tools.common import dataframe_to_records


def preview_dataset_tool(request: PreviewDatasetRequest) -> PreviewDatasetResponse:
    settings = get_settings()
    registry = MetadataRegistry(settings)
    registry.get(request.dataset_id)
    df = load_dataset(request.dataset_id, settings)

    warnings = []
    effective_limit = request.limit
    if effective_limit > settings.max_preview_rows:
        effective_limit = settings.max_preview_rows
        warnings.append(f"limit capped to MAX_PREVIEW_ROWS={settings.max_preview_rows}")

    if request.mode == "head":
        preview_df = df.head(effective_limit)
    elif request.mode == "tail":
        preview_df = df.tail(effective_limit)
    elif request.mode == "sample":
        preview_df = df.sample(n=min(effective_limit, len(df)), random_state=42) if len(df) else df.head(0)
    else:
        raise ToolError("mode must be one of: head, tail, sample", status_code=400, code="invalid_preview_mode")

    pii_columns = detect_pii_columns(preview_df.columns)
    records = dataframe_to_records(preview_df)
    if request.mask_pii and pii_columns:
        records = mask_records(records, pii_columns)

    return PreviewDatasetResponse(
        status="ok",
        dataset_id=request.dataset_id,
        rows_returned=len(records),
        preview=records,
        pii_detected=bool(pii_columns),
        warnings=warnings,
    )
