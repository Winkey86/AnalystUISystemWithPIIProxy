from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from agent_tools.base_agent import BaseAgentTool
from direct_tools.artifacts import load_dataframe


class _DataQualityAgent(BaseAgentTool):
    system_prompt = (
        "Ты — эксперт по качеству данных. "
        "На основе сводки проблем в датасете сформулируй краткие практические рекомендации на русском языке. "
        "Отвечай строго в формате JSON: {\"recommendations\": [\"...\", \"...\"]}. "
        "Не добавляй ничего кроме JSON."
    )


_agent = _DataQualityAgent()


def _compute_issues(df: pd.DataFrame) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    # Null-доли
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            issues.append({"column": col, "issue": "nulls", "count": null_count})

    # Дубликаты
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        issues.append({"column": "_all_", "issue": "duplicate_rows", "count": dup_count})

    # Числовые аномалии: отрицательные значения в колонках с "amount", "price", "qty", "count"
    suspicious_keywords = {"amount", "price", "qty", "count", "quantity", "revenue", "sales"}
    for col in df.select_dtypes(include="number").columns:
        if any(kw in col.lower() for kw in suspicious_keywords):
            neg_count = int((df[col] < 0).sum())
            if neg_count > 0:
                issues.append({"column": col, "issue": "negative_values", "count": neg_count})

    # Выбросы по IQR для числовых колонок
    for col in df.select_dtypes(include="number").columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr
        outlier_count = int(((df[col] < lower) | (df[col] > upper)).sum())
        if outlier_count > 0:
            issues.append({"column": col, "issue": "outliers_iqr", "count": outlier_count})

    # Тип-несоответствия: числовые колонки хранящие строки
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(50)
        numeric_like = sample.apply(lambda v: pd.to_numeric(v, errors="coerce")).notna().mean()
        if numeric_like > 0.8:
            issues.append({"column": col, "issue": "numeric_stored_as_string", "count": None})

    return issues


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def data_quality_agent(artifact_id: str) -> dict[str, Any]:
        """Проверить качество данных в артефакте.

        Проверяет: null-доли, дубликаты, отрицательные значения,
        выбросы (IQR), типы колонок. Возвращает список проблем и рекомендации.

        Args:
            artifact_id: ID артефакта для проверки.

        Returns:
            {
                "status": "ok" | "warning" | "error",
                "artifact_id": str,
                "row_count": int,
                "column_count": int,
                "issues": list[dict],
                "recommendations": list[str]
            }
        """
        try:
            df = load_dataframe(artifact_id)
        except FileNotFoundError:
            return {"status": "error", "error": f"Artifact not found: {artifact_id}"}

        issues = _compute_issues(df)

        recommendations: list[str] = []
        if issues:
            issues_summary = "\n".join(
                f"- column={i['column']}, issue={i['issue']}, count={i['count']}"
                for i in issues
            )
            prompt = (
                f"Датасет содержит {len(df)} строк, {len(df.columns)} колонок.\n"
                f"Найдены проблемы:\n{issues_summary}\n"
                "Дай краткие рекомендации."
            )
            try:
                response = _agent._call_llm_sync([{"role": "user", "content": prompt}])
                parsed = _agent._parse_json_response(response)
                recommendations = parsed.get("recommendations", [])
                if not isinstance(recommendations, list):
                    recommendations = [str(parsed)]
            except Exception:
                recommendations = ["Не удалось получить рекомендации от LLM — проверьте наличие LLM-провайдера."]

        return {
            "status": "warning" if issues else "ok",
            "artifact_id": artifact_id,
            "row_count": len(df),
            "column_count": len(df.columns),
            "issues": issues,
            "recommendations": recommendations,
        }
