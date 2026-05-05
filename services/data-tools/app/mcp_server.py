from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.artifact_store import ensure_dirs
from app.contracts import (
    InspectSchemaRequest,
    LoadDatasetRequest,
    PreviewDatasetRequest,
    ProfileQualityRequest,
    SafeSqlPreviewRequest,
    SafeSqlQueryRequest,
    ToolError,
)
from app.metadata_registry import MetadataRegistry
from app.tools.inspect_schema import inspect_schema_tool
from app.tools.list_datasets import list_datasets_tool
from app.tools.load_dataset import load_dataset_tool
from app.tools.preview_dataset import preview_dataset_tool
from app.tools.profile_quality import profile_quality_tool
from app.tools.safe_sql import safe_sql_preview_tool, safe_sql_query_tool

mcp = FastMCP("data-tools-mcp", host="0.0.0.0", port=8091)


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_model_dump(item) for item in value]
    return value


def _tool_error(exc: ToolError) -> dict[str, Any]:
    return {"status": "error", "code": exc.code, "error": exc.message}


@mcp.custom_route("/health", methods=["GET"])
async def _health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "data-tools-mcp"})


@mcp.tool()
def list_datasets() -> dict[str, Any]:
    """List registered datasets from the metadata registry without returning dataset rows."""
    try:
        return {"status": "ok", "datasets": _model_dump(list_datasets_tool())}
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def load_dataset(
    path: str,
    format: str,
    source_type: str = "file",
    dataset_name: str | None = None,
    overwrite: bool = False,
    options: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Load a CSV, XLSX, JSON, or Parquet file from DATA_INPUT_DIR into a parquet dataset artifact."""
    try:
        request = LoadDatasetRequest(
            request_id=request_id,
            source_type=source_type,
            path=path,
            format=format,
            dataset_name=dataset_name,
            overwrite=overwrite,
            options=options or {},
        )
        return _model_dump(load_dataset_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def inspect_schema(
    dataset_id: str,
    include_examples: bool = True,
    max_examples_per_column: int = 3,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Inspect registered dataset schema, column stats, examples, and PII hints."""
    try:
        request = InspectSchemaRequest(
            request_id=request_id,
            dataset_id=dataset_id,
            include_examples=include_examples,
            max_examples_per_column=max_examples_per_column,
        )
        return _model_dump(inspect_schema_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def preview_dataset(
    dataset_id: str,
    mode: str = "head",
    limit: int = 10,
    mask_pii: bool = True,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a bounded head, tail, or sample preview with optional PII masking."""
    try:
        request = PreviewDatasetRequest(
            request_id=request_id,
            dataset_id=dataset_id,
            mode=mode,
            limit=limit,
            mask_pii=mask_pii,
        )
        return _model_dump(preview_dataset_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def profile_quality(dataset_id: str, request_id: str | None = None) -> dict[str, Any]:
    """Compute a deterministic data quality profile for a registered dataset."""
    try:
        request = ProfileQualityRequest(request_id=request_id, dataset_id=dataset_id)
        return _model_dump(profile_quality_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def safe_sql_preview(dataset_id: str, sql: str, request_id: str | None = None) -> dict[str, Any]:
    """Validate read-only SQL against a registered dataset without executing it."""
    try:
        request = SafeSqlPreviewRequest(request_id=request_id, dataset_id=dataset_id, sql=sql)
        return _model_dump(safe_sql_preview_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


@mcp.tool()
def safe_sql_query(
    dataset_id: str,
    sql: str,
    limit: int = 100,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Execute read-only SQL through DuckDB and store the bounded result as a parquet artifact."""
    try:
        request = SafeSqlQueryRequest(request_id=request_id, dataset_id=dataset_id, sql=sql, limit=limit)
        return _model_dump(safe_sql_query_tool(request))
    except ToolError as exc:
        return _tool_error(exc)


if __name__ == "__main__":
    ensure_dirs()
    MetadataRegistry().ensure()
    mcp.run(transport="sse")
