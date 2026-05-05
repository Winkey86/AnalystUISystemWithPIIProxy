from typing import List

import pandas as pd

from app.artifact_store import load_dataset
from app.contracts import ProfileQualityRequest, ProfileQualityResponse, QualityIssue
from app.metadata_registry import MetadataRegistry


NUMERIC_VALUE_HINTS = ("amount", "price", "revenue", "quantity", "count", "total")
DATETIME_HINTS = ("date", "datetime", "timestamp")


def profile_quality_tool(request: ProfileQualityRequest) -> ProfileQualityResponse:
    registry = MetadataRegistry()
    registry.get(request.dataset_id)
    df = load_dataset(request.dataset_id)
    issues: List[QualityIssue] = []
    rows = len(df)

    for column in df.columns:
        series = df[column]
        null_count = int(series.isna().sum())
        if null_count > 0:
            issues.append(
                QualityIssue(
                    column=str(column),
                    issue="nulls",
                    count=null_count,
                    severity=_null_severity(null_count, rows),
                )
            )

        if _is_empty_column(series):
            issues.append(QualityIssue(column=str(column), issue="empty_column", count=rows, severity="high"))
            continue

        unique_count = int(series.dropna().nunique())
        if rows > 0 and unique_count == 1:
            issues.append(QualityIssue(column=str(column), issue="constant_column", count=rows, severity="low"))

        normalized_name = str(column).lower()
        if any(hint in normalized_name for hint in NUMERIC_VALUE_HINTS):
            negative_count = _negative_count(series)
            if negative_count > 0:
                issues.append(
                    QualityIssue(
                        column=str(column),
                        issue="negative_values",
                        count=negative_count,
                        severity="medium",
                    )
                )

        if any(hint in normalized_name for hint in DATETIME_HINTS):
            invalid_count = _invalid_datetime_count(series)
            if invalid_count > 0:
                issues.append(
                    QualityIssue(
                        column=str(column),
                        issue="invalid_datetime_guess",
                        count=invalid_count,
                        severity="medium",
                    )
                )

    duplicate_count = int(df.duplicated().sum()) if rows else 0
    if duplicate_count > 0:
        severity = "high" if duplicate_count / rows >= 0.1 else "medium"
        issues.append(QualityIssue(column=None, issue="duplicate_rows", count=duplicate_count, severity=severity))

    return ProfileQualityResponse(
        status="warning" if issues else "ok",
        dataset_id=request.dataset_id,
        issues=issues,
    )


def _null_severity(null_count: int, rows: int) -> str:
    if rows == 0:
        return "low"
    ratio = null_count / rows
    if ratio >= 0.5:
        return "high"
    if ratio >= 0.1:
        return "medium"
    return "low"


def _is_empty_column(series: pd.Series) -> bool:
    if len(series) == 0:
        return False
    if series.isna().all():
        return True
    non_null = series.dropna()
    if len(non_null) == 0:
        return True
    return bool(non_null.astype(str).str.strip().eq("").all())


def _negative_count(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce")
    return int((numeric < 0).sum())


def _invalid_datetime_count(series: pd.Series) -> int:
    non_null = series.dropna()
    if len(non_null) == 0:
        return 0
    parsed = pd.to_datetime(non_null, errors="coerce")
    return int(parsed.isna().sum())
