from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from time import perf_counter
import uuid

import duckdb

from app.artifact_store import resolve_artifact_uri, save_query_result
from app.config import get_settings
from app.contracts import SafeSqlPreviewRequest, SafeSqlPreviewResponse, SafeSqlQueryRequest, SafeSqlQueryResponse, ToolError
from app.metadata_registry import MetadataRegistry
from app.security.sql_guard import guard_sql
from app.tools.common import dataframe_to_records


def safe_sql_preview_tool(request: SafeSqlPreviewRequest) -> SafeSqlPreviewResponse:
    registry = MetadataRegistry()
    registry.get(request.dataset_id)
    guard = guard_sql(request.sql)
    return SafeSqlPreviewResponse(
        status=guard.status,
        is_read_only=guard.is_read_only,
        estimated_safe=guard.estimated_safe,
        blocked_operations=guard.blocked_operations,
        normalized_sql=guard.normalized_sql,
    )


def safe_sql_query_tool(request: SafeSqlQueryRequest) -> SafeSqlQueryResponse:
    settings = get_settings()
    registry = MetadataRegistry(settings)
    metadata = registry.get(request.dataset_id)
    guard = guard_sql(request.sql)
    if not guard.estimated_safe or guard.normalized_sql is None:
        return SafeSqlQueryResponse(
            status="blocked",
            dataset_id=request.dataset_id,
            rows_returned=0,
            preview=[],
            execution_ms=0,
            blocked_operations=guard.blocked_operations,
        )

    effective_limit = min(request.limit, settings.max_query_rows)
    artifact_path = resolve_artifact_uri(metadata.artifact_uri, settings)
    started = perf_counter()
    result_df = _execute_query_with_timeout(
        artifact_path=artifact_path,
        dataset_id=request.dataset_id,
        sql=guard.normalized_sql,
        limit=effective_limit,
        timeout_seconds=settings.query_timeout_seconds,
    )
    execution_ms = int((perf_counter() - started) * 1000)

    query_id = f"q_{request.dataset_id}_{uuid.uuid4().hex[:10]}".replace("-", "_")
    result_uri = save_query_result(result_df, query_id, settings)
    preview_limit = min(settings.max_preview_rows, len(result_df))
    preview = dataframe_to_records(result_df.head(preview_limit))

    return SafeSqlQueryResponse(
        status="ok",
        dataset_id=request.dataset_id,
        result_artifact_uri=result_uri,
        rows_returned=len(result_df),
        preview=preview,
        execution_ms=execution_ms,
    )


def _execute_query_with_timeout(
    artifact_path: Path,
    dataset_id: str,
    sql: str,
    limit: int,
    timeout_seconds: int,
):
    connection_holder = {}

    def run():
        connection = duckdb.connect(database=":memory:")
        connection_holder["connection"] = connection
        try:
            _register_dataset_views(connection, artifact_path, dataset_id)
            wrapped_sql = f"SELECT * FROM ({sql}) AS q LIMIT {int(limit)}"
            return connection.execute(wrapped_sql).fetchdf()
        finally:
            connection.close()

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(run)
    try:
        result = future.result(timeout=timeout_seconds)
        executor.shutdown(wait=True)
        return result
    except FutureTimeoutError as exc:
        connection = connection_holder.get("connection")
        interrupt = getattr(connection, "interrupt", None)
        if interrupt is not None:
            interrupt()
        executor.shutdown(wait=False, cancel_futures=True)
        raise ToolError("SQL query timed out", status_code=408, code="query_timeout") from exc


def _register_dataset_views(connection, artifact_path: Path, dataset_id: str) -> None:
    parquet_path = str(artifact_path).replace("\\", "/").replace("'", "''")
    table_names = {dataset_id, dataset_id.replace("-", "_")}
    for table_name in table_names:
        connection.execute(
            f"CREATE VIEW {_quote_identifier(table_name)} AS SELECT * FROM read_parquet('{parquet_path}')"
        )


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
