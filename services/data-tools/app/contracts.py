from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "tool_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class BaseToolRequest(BaseModel):
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "data-tools"
    deterministic: bool = True


class LoadDatasetRequest(BaseToolRequest):
    source_type: str = "file"
    path: str
    format: str
    dataset_name: Optional[str] = None
    overwrite: bool = False
    options: Dict[str, Any] = Field(default_factory=dict)


class SchemaSummary(BaseModel):
    rows: int
    columns: int


class LoadDatasetResponse(BaseModel):
    status: str
    dataset_id: str
    artifact_uri: str
    schema_summary: SchemaSummary
    warnings: List[str] = Field(default_factory=list)


class InspectSchemaRequest(BaseToolRequest):
    dataset_id: str
    include_examples: bool = True
    max_examples_per_column: int = Field(default=3, ge=0)


class ColumnInspection(BaseModel):
    name: str
    dtype: str
    nullable: bool
    null_count: int
    unique_count: int
    example_values: List[Any] = Field(default_factory=list)
    pii_hint: bool


class InspectSchemaResponse(BaseModel):
    status: str
    dataset_id: str
    columns: List[ColumnInspection]


class PreviewDatasetRequest(BaseToolRequest):
    dataset_id: str
    mode: str = "head"
    limit: int = Field(default=10, ge=1)
    mask_pii: bool = True


class PreviewDatasetResponse(BaseModel):
    status: str
    dataset_id: str
    rows_returned: int
    preview: List[Dict[str, Any]]
    pii_detected: bool
    warnings: List[str] = Field(default_factory=list)


class ProfileQualityRequest(BaseToolRequest):
    dataset_id: str


class QualityIssue(BaseModel):
    column: Optional[str] = None
    issue: str
    count: int
    severity: str


class ProfileQualityResponse(BaseModel):
    status: str
    dataset_id: str
    issues: List[QualityIssue]


class SafeSqlPreviewRequest(BaseToolRequest):
    dataset_id: str
    sql: str


class SafeSqlPreviewResponse(BaseModel):
    status: str
    is_read_only: bool
    estimated_safe: bool
    blocked_operations: List[str] = Field(default_factory=list)
    normalized_sql: Optional[str] = None


class SafeSqlQueryRequest(BaseToolRequest):
    dataset_id: str
    sql: str
    limit: int = Field(default=100, ge=1)


class SafeSqlQueryResponse(BaseModel):
    status: str
    dataset_id: str
    result_artifact_uri: Optional[str] = None
    rows_returned: int = 0
    preview: List[Dict[str, Any]] = Field(default_factory=list)
    execution_ms: int = 0
    blocked_operations: List[str] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    dataset_id: str
    artifact_uri: str
    local_path: str
    rows: int
    columns: int
    dtypes: Dict[str, str]
    created_at: str
    source_path: str
    source_format: str
    pii_columns: List[str] = Field(default_factory=list)


class ToolCallLog(BaseModel):
    timestamp: str
    request_id: str
    tool_name: str
    dataset_id: Optional[str] = None
    status: str
    latency_ms: int
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    request_id: str
    code: str
    error: str
