from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from config import settings
from direct_tools.artifacts import load_dataframe


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def preview_dataset(artifact_id: str, n: int = 10) -> dict[str, Any]:
        """Первые N строк датасета из артефакта.

        Args:
            artifact_id: ID артефакта.
            n: Количество строк (max 100).
        """
        n = min(n, settings.max_rows_preview)
        df = load_dataframe(artifact_id)
        return {
            "rows": df.head(n).to_dict(orient="records"),
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": list(df.columns),
        }

    @mcp.tool()
    @audited
    def schema_inspect(artifact_id: str) -> dict[str, Any]:
        """Схема датасета: тип колонки, доля null, число уникальных, примеры значений.

        Args:
            artifact_id: ID артефакта.
        """
        df = load_dataframe(artifact_id)
        columns = []
        for col in df.columns:
            series = df[col]
            null_pct = round(series.isna().mean() * 100, 2)
            n_unique = int(series.nunique(dropna=True))
            examples: list[Any] = series.dropna().head(3).tolist()
            columns.append(
                {
                    "name": col,
                    "dtype": str(series.dtype),
                    "null_pct": null_pct,
                    "n_unique": n_unique,
                    "examples": [str(v) for v in examples],
                }
            )
        return {
            "artifact_id": artifact_id,
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": columns,
        }
