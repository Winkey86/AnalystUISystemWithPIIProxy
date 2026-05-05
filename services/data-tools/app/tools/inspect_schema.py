from app.artifact_store import load_dataset
from app.contracts import ColumnInspection, InspectSchemaRequest, InspectSchemaResponse
from app.metadata_registry import MetadataRegistry
from app.security.pii_column_detector import has_pii_hint
from app.tools.common import json_safe_value


MAX_EXAMPLES_PER_COLUMN = 10


def inspect_schema_tool(request: InspectSchemaRequest) -> InspectSchemaResponse:
    registry = MetadataRegistry()
    registry.get(request.dataset_id)
    df = load_dataset(request.dataset_id)
    max_examples = min(request.max_examples_per_column, MAX_EXAMPLES_PER_COLUMN)

    columns = []
    for column in df.columns:
        series = df[column]
        non_null = series.dropna()
        examples = []
        if request.include_examples and max_examples > 0:
            for value in non_null.drop_duplicates().head(max_examples).tolist():
                examples.append(json_safe_value(value))
        columns.append(
            ColumnInspection(
                name=str(column),
                dtype=str(series.dtype),
                nullable=bool(series.isna().any()),
                null_count=int(series.isna().sum()),
                unique_count=int(series.nunique(dropna=True)),
                example_values=examples,
                pii_hint=has_pii_hint(str(column)),
            )
        )

    return InspectSchemaResponse(status="ok", dataset_id=request.dataset_id, columns=columns)
