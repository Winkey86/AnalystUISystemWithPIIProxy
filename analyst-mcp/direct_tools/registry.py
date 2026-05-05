from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

# Инструмент регистрируется последним — после всех остальных,
# поэтому импортируем mcp только внутри функции.


_TOOL_DESCRIPTIONS: list[dict[str, str]] = [
    {"name": "tool_registry", "category": "direct", "description": "Список всех доступных инструментов с категориями."},
    {"name": "metadata_lookup", "category": "direct", "description": "Описание датасета, словарь колонок, единицы измерений."},
    {"name": "metadata_list", "category": "direct", "description": "Список датасетов с сохранёнными метаданными."},
    {"name": "artifact_store", "category": "direct", "description": "Сохранить табличный артефакт (list[dict]) в parquet/json."},
    {"name": "artifact_load", "category": "direct", "description": "Загрузить артефакт по artifact_id."},
    {"name": "artifact_list", "category": "direct", "description": "Список сохранённых artifact_id."},
    {"name": "artifact_delete", "category": "direct", "description": "Удалить артефакт."},
    {"name": "preview_dataset", "category": "direct", "description": "Первые N строк артефакта."},
    {"name": "schema_inspect", "category": "direct", "description": "Типы, null-доли, примеры значений по колонкам."},
    {"name": "json_parse", "category": "direct", "description": "Разобрать JSON-строку в объект."},
    {"name": "json_validate", "category": "direct", "description": "Валидировать JSON против JSON Schema."},
    {"name": "excel_sheet_list", "category": "direct", "description": "Список листов Excel-файла."},
    {"name": "excel_preview", "category": "direct", "description": "Просмотр строк листа Excel."},
    {"name": "safe_sql_preview", "category": "direct", "description": "Нормализация и проверка SELECT без выполнения."},
    {"name": "result_formatter", "category": "direct", "description": "Форматирование секций в Markdown-ответ."},
    {"name": "get_audit_log", "category": "direct", "description": "Лог шагов метакоординации."},
    {"name": "data_source_agent", "category": "agent-tool", "description": "Загрузка данных из CSV, Excel, JSON, Parquet, БД, API."},
    {"name": "data_quality_agent", "category": "agent-tool", "description": "Проверка качества данных, рекомендации."},
    {"name": "transformation_agent", "category": "agent-tool", "description": "Фильтрация, агрегация, join, нормализация данных."},
    {"name": "sql_analysis_agent", "category": "agent-tool", "description": "Аналитика SELECT-запросами через DuckDB."},
    {"name": "python_analytics_agent", "category": "agent-tool", "description": "Статистика, выбросы, кластеризация, тесты."},
    {"name": "visualization_agent", "category": "agent-tool", "description": "Генерация графиков (PNG/HTML)."},
    {"name": "reporting_agent", "category": "agent-tool", "description": "Сборка финального отчёта."},
]


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def tool_registry() -> dict[str, Any]:
        """Список всех доступных инструментов с категориями (direct / agent-tool)."""
        return {"tools": _TOOL_DESCRIPTIONS}
