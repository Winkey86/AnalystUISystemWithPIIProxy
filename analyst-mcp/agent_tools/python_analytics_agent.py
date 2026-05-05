from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import scipy.stats as stats

from agent_tools.base_agent import BaseAgentTool
from direct_tools.artifacts import load_dataframe

_ANALYSIS_TYPES = {
    "describe", "correlation", "outliers",
    "statistical_test", "cluster", "timeseries", "feature_importance",
}


class _AnalyticsAgent(BaseAgentTool):
    system_prompt = (
        "Ты — аналитик данных. Тебе передают числовые результаты вычислений. "
        "Дай краткую интерпретацию на русском языке. "
        "Отвечай строго в формате JSON: {\"interpretation\": \"...\"}. "
        "Не добавляй ничего кроме JSON."
    )


_agent = _AnalyticsAgent()


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def python_analytics_agent(
        artifact_id: str,
        analysis_type: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Выполнить аналитику на Python (статистика, тесты, кластеризация и др.).

        Args:
            artifact_id: ID артефакта.
            analysis_type: Тип анализа:
                - 'describe'           — describe() + форма данных
                - 'correlation'        — корреляционная матрица (Pearson)
                - 'outliers'           — поиск выбросов (IQR)
                - 'statistical_test'   — t-test или Mann-Whitney (params: col, group_col)
                - 'cluster'            — KMeans (params: columns, n_clusters)
                - 'timeseries'         — тренд/сезонность (params: date_col, value_col)
                - 'feature_importance' — RandomForest importances (params: target_col)
            params: Дополнительные параметры зависят от analysis_type.

        Returns:
            {
                "status": "ok" | "error",
                "analysis_type": str,
                "result": dict,
                "interpretation": str
            }
        """
        if analysis_type not in _ANALYSIS_TYPES:
            return {"status": "error", "error": f"Unknown analysis_type. Choose from: {_ANALYSIS_TYPES}"}

        params = params or {}
        try:
            df = load_dataframe(artifact_id)
        except FileNotFoundError:
            return {"status": "error", "error": f"Artifact not found: {artifact_id}"}

        try:
            result = _run(df, analysis_type, params)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        interpretation = ""
        try:
            summary = str(result)[:1000]
            response = _agent._call_llm_sync([
                {"role": "user", "content": f"Тип анализа: {analysis_type}\nРезультат: {summary}"}
            ])
            parsed = _agent._parse_json_response(response)
            interpretation = parsed.get("interpretation", "")
        except Exception:
            interpretation = "Интерпретация недоступна (LLM не отвечает)."

        return {
            "status": "ok",
            "analysis_type": analysis_type,
            "result": result,
            "interpretation": interpretation,
        }


def _run(df: pd.DataFrame, analysis_type: str, params: dict) -> dict[str, Any]:
    num_df = df.select_dtypes(include="number")

    if analysis_type == "describe":
        desc = num_df.describe().round(4).to_dict()
        return {"describe": desc, "shape": list(df.shape)}

    if analysis_type == "correlation":
        corr = num_df.corr(method="pearson").round(4).to_dict()
        return {"correlation_matrix": corr}

    if analysis_type == "outliers":
        result: dict[str, Any] = {}
        for col in num_df.columns:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = df[(df[col] < lower) | (df[col] > upper)][col]
            result[col] = {
                "count": int(len(outliers)),
                "lower_bound": round(float(lower), 4),
                "upper_bound": round(float(upper), 4),
            }
        return {"outliers_by_column": result}

    if analysis_type == "statistical_test":
        col: str = params.get("col", "")
        group_col: str = params.get("group_col", "")
        if not col or not group_col:
            raise ValueError("'col' and 'group_col' required for statistical_test")
        groups = [g[col].dropna().values for _, g in df.groupby(group_col)]
        if len(groups) != 2:
            raise ValueError("statistical_test requires exactly 2 groups")
        t_stat, p_value = stats.ttest_ind(*groups)
        u_stat, p_mann = stats.mannwhitneyu(*groups, alternative="two-sided")
        return {
            "col": col, "group_col": group_col,
            "t_test": {"t_stat": round(float(t_stat), 4), "p_value": round(float(p_value), 4)},
            "mann_whitney": {"u_stat": round(float(u_stat), 4), "p_value": round(float(p_mann), 4)},
        }

    if analysis_type == "cluster":
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        columns: list[str] = params.get("columns", list(num_df.columns))
        n_clusters: int = params.get("n_clusters", 3)
        X = df[columns].dropna()
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = km.fit_predict(X_scaled)
        sizes = pd.Series(labels).value_counts().sort_index().to_dict()
        return {
            "n_clusters": n_clusters,
            "cluster_sizes": {str(k): int(v) for k, v in sizes.items()},
            "inertia": round(float(km.inertia_), 4),
        }

    if analysis_type == "timeseries":
        from statsmodels.tsa.seasonal import seasonal_decompose

        date_col: str = params.get("date_col", "")
        value_col: str = params.get("value_col", "")
        if not date_col or not value_col:
            raise ValueError("'date_col' and 'value_col' required for timeseries")
        ts = df[[date_col, value_col]].copy()
        ts[date_col] = pd.to_datetime(ts[date_col])
        ts = ts.sort_values(date_col).set_index(date_col)[value_col].dropna()
        period = params.get("period", 12)
        if len(ts) < 2 * period:
            return {"trend": ts.to_list(), "note": "Too few data points for decomposition"}
        decomp = seasonal_decompose(ts, model="additive", period=period)
        return {
            "trend": [round(v, 4) for v in decomp.trend.dropna().tolist()],
            "seasonal": [round(v, 4) for v in decomp.seasonal.dropna().tolist()[:period]],
        }

    if analysis_type == "feature_importance":
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.preprocessing import LabelEncoder

        target_col: str = params.get("target_col", "")
        if not target_col:
            raise ValueError("'target_col' required for feature_importance")
        feature_cols = [c for c in num_df.columns if c != target_col]
        if not feature_cols:
            raise ValueError("No numeric feature columns found")
        X = df[feature_cols].dropna()
        y = df.loc[X.index, target_col]
        if y.dtype == object:
            y = LabelEncoder().fit_transform(y)
            model = RandomForestClassifier(n_estimators=50, random_state=42)
        else:
            model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X, y)
        importance = {c: round(float(v), 4) for c, v in zip(feature_cols, model.feature_importances_)}
        return {"feature_importance": dict(sorted(importance.items(), key=lambda x: -x[1]))}

    raise ValueError(f"Unhandled analysis_type: {analysis_type}")
