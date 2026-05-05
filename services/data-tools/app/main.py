from pathlib import Path
from time import perf_counter
from typing import Callable
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.artifact_store import ensure_dirs
from app.contracts import (
    ErrorResponse,
    HealthResponse,
    InspectSchemaRequest,
    LoadDatasetRequest,
    PreviewDatasetRequest,
    ProfileQualityRequest,
    SafeSqlPreviewRequest,
    SafeSqlQueryRequest,
    ToolError,
)
from app.logging_utils import log_tool_call, request_id_or_new
from app.metadata_registry import MetadataRegistry
from app.tools.inspect_schema import inspect_schema_tool
from app.tools.list_datasets import list_datasets_tool
from app.tools.load_dataset import load_dataset_tool
from app.tools.preview_dataset import preview_dataset_tool
from app.tools.profile_quality import profile_quality_tool
from app.tools.safe_sql import safe_sql_preview_tool, safe_sql_query_tool


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    MetadataRegistry().ensure()
    yield


app = FastAPI(title="Deterministic Data Tools", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "code": "validation_error",
            "error": str(exc),
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/tools")
def tools():
    manifest_path = Path(__file__).resolve().parents[1] / "tool_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@app.get("/datasets")
def datasets():
    return _run_tool_no_body("list_datasets", list_datasets_tool)


@app.post("/tools/load_dataset")
def load_dataset(request: LoadDatasetRequest):
    return _run_tool("load_dataset", request, load_dataset_tool)


@app.post("/tools/inspect_schema")
def inspect_schema(request: InspectSchemaRequest):
    return _run_tool("inspect_schema", request, inspect_schema_tool)


@app.post("/tools/preview_dataset")
def preview_dataset(request: PreviewDatasetRequest):
    return _run_tool("preview_dataset", request, preview_dataset_tool)


@app.post("/tools/profile_quality")
def profile_quality(request: ProfileQualityRequest):
    return _run_tool("profile_quality", request, profile_quality_tool)


@app.post("/tools/safe_sql_preview")
def safe_sql_preview(request: SafeSqlPreviewRequest):
    return _run_tool("safe_sql_preview", request, safe_sql_preview_tool)


@app.post("/tools/safe_sql_query")
def safe_sql_query(request: SafeSqlQueryRequest):
    return _run_tool("safe_sql_query", request, safe_sql_query_tool)


def _run_tool(tool_name: str, request, func: Callable):
    request_id = request_id_or_new(getattr(request, "request_id", None))
    dataset_id = getattr(request, "dataset_id", None)
    started = perf_counter()
    try:
        result = func(request)
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(
            tool_name=tool_name,
            request_id=request_id,
            dataset_id=dataset_id or getattr(result, "dataset_id", None),
            status=getattr(result, "status", "ok"),
            latency_ms=latency_ms,
        )
        return result
    except ToolError as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(
            tool_name=tool_name,
            request_id=request_id,
            dataset_id=dataset_id,
            status="error",
            latency_ms=latency_ms,
            error=exc.message,
        )
        return _error_response(exc, request_id)
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(
            tool_name=tool_name,
            request_id=request_id,
            dataset_id=dataset_id,
            status="error",
            latency_ms=latency_ms,
            error=str(exc),
        )
        return _error_response(ToolError("Internal tool error", status_code=500, code="internal_error"), request_id)


def _run_tool_no_body(tool_name: str, func: Callable):
    request_id = request_id_or_new(None)
    started = perf_counter()
    try:
        result = func()
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(tool_name=tool_name, request_id=request_id, status="ok", latency_ms=latency_ms)
        return result
    except ToolError as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(
            tool_name=tool_name,
            request_id=request_id,
            status="error",
            latency_ms=latency_ms,
            error=exc.message,
        )
        return _error_response(exc, request_id)
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        log_tool_call(
            tool_name=tool_name,
            request_id=request_id,
            status="error",
            latency_ms=latency_ms,
            error=str(exc),
        )
        return _error_response(ToolError("Internal tool error", status_code=500, code="internal_error"), request_id)


def _error_response(exc: ToolError, request_id: str) -> JSONResponse:
    body = ErrorResponse(request_id=request_id, code=exc.code, error=exc.message)
    return JSONResponse(status_code=exc.status_code, content=_model_dump(body))


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
