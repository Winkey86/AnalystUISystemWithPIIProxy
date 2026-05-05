from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Callable


def _render_table(rows: list[dict]) -> str:
    if not rows:
        return "_Нет данных_"
    headers = list(rows[0].keys())
    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    data_lines = [
        "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
        for row in rows
    ]
    return "\n".join([header_line, sep_line] + data_lines)


def result_formatter(sections: list[dict]) -> str:
    """Собрать список секций в Markdown-ответ.

    Каждая секция — dict с полями:
      - type: "text" | "table" | "image_path" | "image_base64" | "code"
      - content: строка, list[dict] (для table) или dict
      - caption: (опционально) заголовок секции
      - language: (для code) язык, например "python" или "sql"

    Args:
        sections: Список секций.

    Returns:
        Markdown-строка.
    """
    parts: list[str] = []
    for sec in sections:
        sec_type = sec.get("type", "text")
        caption = sec.get("caption", "")
        content = sec.get("content", "")

        if caption:
            parts.append(f"### {caption}\n")

        if sec_type == "text":
            parts.append(str(content))

        elif sec_type == "table":
            rows = content if isinstance(content, list) else []
            parts.append(_render_table(rows))

        elif sec_type == "image_path":
            p = Path(str(content))
            if p.exists():
                img_bytes = p.read_bytes()
                b64 = base64.b64encode(img_bytes).decode()
                ext = p.suffix.lstrip(".").lower() or "png"
                parts.append(f"![{caption or 'chart'}](data:image/{ext};base64,{b64})")
            else:
                parts.append(f"_Изображение не найдено: {content}_")

        elif sec_type == "image_base64":
            b64 = str(content)
            parts.append(f"![{caption or 'chart'}](data:image/png;base64,{b64})")

        elif sec_type == "code":
            lang = sec.get("language", "")
            parts.append(f"```{lang}\n{content}\n```")

        else:
            parts.append(str(content))

        parts.append("")  # пустая строка между секциями

    return "\n".join(parts).strip()


# Присваиваем после определения функции
_module_result_formatter = result_formatter


def register(mcp: Any, audited: Callable) -> None:
    # Регистрируем как MCP-инструмент. Имя совпадает с именем standalone-функции,
    # поэтому используем явный декоратор с name= если FastMCP поддерживает,
    # иначе просто вызываем standalone-функцию внутри обёртки.
    @mcp.tool()
    @audited
    def result_formatter(sections: list[dict]) -> str:
        """Собрать список секций в Markdown-ответ.

        Каждая секция — dict с полями:
          - type: "text" | "table" | "image_path" | "image_base64" | "code"
          - content: строка, list[dict] (для table) или dict
          - caption: (опционально) заголовок секции
          - language: (для code) язык, например "python" или "sql"

        Args:
            sections: Список секций.

        Returns:
            Markdown-строка.
        """
        # Делегируем в модульную standalone-функцию напрямую по ссылке
        return _module_result_formatter(sections)
