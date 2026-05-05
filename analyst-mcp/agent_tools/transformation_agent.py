from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from direct_tools.artifacts import load_dataframe, save_dataframe

_ALLOWED_HOW = {"inner", "left", "right", "outer"}


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def transformation_agent(
        artifact_id: str,
        operation: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Выполнить преобразование датасета и сохранить результат как новый артефакт.

        Args:
            artifact_id: ID исходного артефакта.
            operation: Одна из: 'filter', 'aggregate', 'join', 'sort',
                       'flatten_json', 'normalize', 'drop_nulls', 'rename_columns'.
            params: Параметры операции (зависят от operation):
                    filter:
                      - condition (str): pandas.query()-выражение, например "amount > 0"
                    aggregate:
                      - group_by (list[str]): колонки группировки
                      - agg (dict): {колонка: функция}, например {"revenue": "sum"}
                    join:
                      - right_artifact_id (str): артефакт для правой таблицы
                      - on (str | list[str]): ключ(и) объединения
                      - how (str): 'inner'|'left'|'right'|'outer'
                    sort:
                      - by (list[str]): колонки сортировки
                      - ascending (bool): по умолчанию true
                    flatten_json:
                      - column (str): колонка с JSON-объектами/списками
                    normalize:
                      - columns (list[str]): нормализовать (min-max) указанные колонки
                    drop_nulls:
                      - subset (list[str]): (опц.) только по этим колонкам
                    rename_columns:
                      - mapping (dict): {старое_имя: новое_имя}

        Returns:
            {"status": "ok", "artifact_id": str, "row_count": int, "column_count": int}
        """
        params = params or {}

        try:
            df = load_dataframe(artifact_id)
        except FileNotFoundError:
            return {"status": "error", "error": f"Artifact not found: {artifact_id}"}

        try:
            result_df = _apply(df, operation, params)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        new_id = save_dataframe(result_df, f"{artifact_id}_{operation}")
        return {
            "status": "ok",
            "artifact_id": new_id,
            "row_count": len(result_df),
            "column_count": len(result_df.columns),
        }


def _apply(df: pd.DataFrame, operation: str, params: dict) -> pd.DataFrame:
    if operation == "filter":
        condition = params.get("condition", "")
        if not condition:
            raise ValueError("'condition' is required for filter operation")
        # pandas.query — безопасный DSL, не accept произвольный Python
        return df.query(condition)

    if operation == "aggregate":
        group_by: list[str] = params.get("group_by", [])
        agg: dict = params.get("agg", {})
        if not group_by or not agg:
            raise ValueError("'group_by' and 'agg' are required for aggregate operation")
        return df.groupby(group_by).agg(agg).reset_index()

    if operation == "join":
        right_id: str = params.get("right_artifact_id", "")
        if not right_id:
            raise ValueError("'right_artifact_id' is required for join operation")
        on = params.get("on")
        how = params.get("how", "left")
        if how not in _ALLOWED_HOW:
            raise ValueError(f"'how' must be one of {_ALLOWED_HOW}")
        right_df = load_dataframe(right_id)
        return pd.merge(df, right_df, on=on, how=how)

    if operation == "sort":
        by: list[str] = params.get("by", [])
        ascending: bool = params.get("ascending", True)
        if not by:
            raise ValueError("'by' is required for sort operation")
        return df.sort_values(by=by, ascending=ascending)

    if operation == "flatten_json":
        col: str = params.get("column", "")
        if not col:
            raise ValueError("'column' is required for flatten_json operation")
        normalized = pd.json_normalize(df[col].dropna().tolist())
        return pd.concat([df.drop(columns=[col]).reset_index(drop=True), normalized], axis=1)

    if operation == "normalize":
        columns: list[str] = params.get("columns", list(df.select_dtypes(include="number").columns))
        result = df.copy()
        for c in columns:
            col_min = result[c].min()
            col_max = result[c].max()
            if col_max != col_min:
                result[c] = (result[c] - col_min) / (col_max - col_min)
        return result

    if operation == "drop_nulls":
        subset: list[str] | None = params.get("subset") or None
        return df.dropna(subset=subset)

    if operation == "rename_columns":
        mapping: dict[str, str] = params.get("mapping", {})
        if not mapping:
            raise ValueError("'mapping' is required for rename_columns operation")
        return df.rename(columns=mapping)

    raise ValueError(f"Unknown operation: {operation!r}")
