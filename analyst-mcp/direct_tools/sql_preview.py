from __future__ import annotations

from typing import Any, Callable

import sqlglot
import sqlglot.expressions as exp


def _safe_sql_preview(query: str) -> dict[str, Any]:
    """Нормализовать и проверить SQL-запрос без выполнения (standalone, для import).

    Args:
        query: SQL-строка.

    Returns:
        {
            "normalized": str,
            "is_select": bool,
            "tables": list[str],
            "has_joins": bool,
            "has_aggregations": bool,
            "estimated_complexity": "simple" | "moderate" | "complex",
            "error": str  # только при ошибке парсинга
        }
    """
    try:
        statements = sqlglot.parse(query)
    except sqlglot.errors.ParseError as exc:
        return {"error": f"SQL parse error: {exc}", "is_select": False}

    if not statements or statements[0] is None:
        return {"error": "Empty query", "is_select": False}

    stmt = statements[0]

    is_select = isinstance(stmt, exp.Select)
    normalized = stmt.sql(dialect="duckdb", pretty=False)
    tables = [t.name for t in stmt.find_all(exp.Table) if t.name]
    has_joins = bool(list(stmt.find_all(exp.Join)))
    agg_types = (exp.Sum, exp.Avg, exp.Count, exp.Max, exp.Min)
    has_aggregations = any(stmt.find(a) for a in agg_types)

    if has_joins and has_aggregations:
        complexity = "complex"
    elif has_joins or has_aggregations:
        complexity = "moderate"
    else:
        complexity = "simple"

    return {
        "normalized": normalized,
        "is_select": is_select,
        "tables": tables,
        "has_joins": has_joins,
        "has_aggregations": has_aggregations,
        "estimated_complexity": complexity,
    }


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def safe_sql_preview(query: str) -> dict[str, Any]:
        """Нормализовать и проверить SQL-запрос без выполнения.

        Проверяет, что запрос является SELECT (без DDL/DML).
        Извлекает задействованные таблицы и оценивает сложность.

        Args:
            query: SQL-строка.

        Returns:
            {
                "normalized": str,
                "is_select": bool,
                "tables": list[str],
                "has_joins": bool,
                "has_aggregations": bool,
                "estimated_complexity": "simple" | "moderate" | "complex",
                "error": str  # только при ошибке парсинга
            }
        """
        # Делегируем в модульную standalone-функцию
        return _safe_sql_preview(query)
