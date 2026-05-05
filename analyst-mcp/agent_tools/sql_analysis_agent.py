from __future__ import annotations

from typing import Any, Callable

import duckdb
import pandas as pd

from agent_tools.base_agent import BaseAgentTool
from direct_tools.artifacts import load_dataframe, save_dataframe
from direct_tools.sql_preview import _safe_sql_preview as safe_sql_preview


class _SQLAgent(BaseAgentTool):
    system_prompt = (
        "Ты — SQL-аналитик. Тебе передают описание аналитической задачи и схему таблицы. "
        "Напиши один SQL SELECT-запрос для DuckDB. "
        "Отвечай строго в формате JSON: {\"query\": \"SELECT ...\", \"explanation\": \"...\"}. "
        "Используй только SELECT. Никаких INSERT/UPDATE/DELETE/DROP/CREATE."
    )


_agent = _SQLAgent()


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def sql_analysis_agent(
        artifact_id: str,
        task_description: str,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Выполнить аналитику через SQL SELECT над артефактом (DuckDB).

        Если query не передан — LLM генерирует запрос по task_description.
        Запросы, не являющиеся SELECT, отклоняются.

        Args:
            artifact_id: ID артефакта (таблица доступна как 'df').
            task_description: Описание задачи на естественном языке.
            query: (опц.) Готовый SQL SELECT-запрос — LLM не будет вызван.

        Returns:
            {
                "status": "ok" | "error",
                "query": str,
                "explanation": str,
                "rows": list[dict],
                "row_count": int
            }
        """
        try:
            df = load_dataframe(artifact_id)
        except FileNotFoundError:
            return {"status": "error", "error": f"Artifact not found: {artifact_id}"}

        if not query:
            schema_lines = [f"  {c} ({t})" for c, t in df.dtypes.items()]
            schema_str = "\n".join(schema_lines)
            prompt = (
                f"Таблица называется 'df'. Схема:\n{schema_str}\n\n"
                f"Задача: {task_description}"
            )
            try:
                response = _agent._call_llm_sync([{"role": "user", "content": prompt}])
                parsed = _agent._parse_json_response(response)
                query = parsed.get("query", "")
                explanation = parsed.get("explanation", "")
            except Exception as exc:
                return {"status": "error", "error": f"LLM call failed: {exc}"}
        else:
            explanation = task_description

        if not query:
            return {"status": "error", "error": "Could not generate SQL query"}

        # Безопасность: проверяем через sqlglot перед выполнением
        preview = safe_sql_preview(query=query)
        if preview.get("error"):
            return {"status": "error", "error": preview["error"]}
        if not preview.get("is_select"):
            return {"status": "error", "error": "Only SELECT queries are allowed"}

        try:
            result_df = duckdb.query_df(df, "df", query).df()
        except Exception as exc:
            return {"status": "error", "error": f"DuckDB error: {exc}"}

        result_df = result_df.head(500)
        return {
            "status": "ok",
            "query": query,
            "explanation": explanation,
            "rows": result_df.to_dict(orient="records"),
            "row_count": len(result_df),
        }
