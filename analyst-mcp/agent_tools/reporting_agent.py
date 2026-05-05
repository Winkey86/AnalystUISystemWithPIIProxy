from __future__ import annotations

from typing import Any, Callable

from agent_tools.base_agent import BaseAgentTool
from direct_tools.artifacts import load_dataframe, save_dataframe
from direct_tools.formatter import result_formatter as _render_report


class _ReportingAgent(BaseAgentTool):
    system_prompt = (
        "Ты — аналитик-редактор. Тебе передают секции аналитического отчёта. "
        "Напиши краткое executive summary на русском языке (3–7 предложений). "
        "Отвечай строго в формате JSON: {\"summary\": \"...\"}. "
        "Не добавляй ничего кроме JSON."
    )


_agent = _ReportingAgent()


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def reporting_agent(
        sections: list[dict],
        report_name: str = "report",
        format: str = "markdown",
    ) -> dict[str, Any]:
        """Собрать финальный отчёт из секций аналитики.

        Генерирует executive summary через LLM и форматирует все секции в Markdown.
        При format='markdown' возвращает текст и сохраняет как артефакт.

        Args:
            sections: Список секций — см. result_formatter для деталей формата.
                      Примеры type: 'text', 'table', 'image_path', 'code'.
            report_name: Базовое имя для артефакта.
            format: 'markdown' (по умолчанию).

        Returns:
            {
                "status": "ok" | "error",
                "summary": str,
                "report": str,
                "artifact_id": str
            }
        """
        # Генерируем summary через LLM
        section_texts = []
        for sec in sections:
            caption = sec.get("caption", "")
            sec_type = sec.get("type", "text")
            content = sec.get("content", "")
            if sec_type == "table" and isinstance(content, list):
                preview = str(content[:3])
            else:
                preview = str(content)[:500]
            section_texts.append(f"[{sec_type}] {caption}: {preview}")

        summary = ""
        try:
            response = _agent._call_llm_sync([
                {"role": "user", "content": "Секции отчёта:\n" + "\n".join(section_texts)}
            ])
            parsed = _agent._parse_json_response(response)
            summary = parsed.get("summary", "")
        except Exception:
            summary = "Автоматическое резюме недоступно."

        # Prepend summary section
        full_sections = [{"type": "text", "caption": "Резюме", "content": summary}] + list(sections)
        report_md = _render_report(sections=full_sections)

        # Сохраняем как артефакт
        artifact_id = save_dataframe(
            __import__("pandas").DataFrame([{"report": report_md}]),
            report_name,
        )

        return {
            "status": "ok",
            "summary": summary,
            "report": report_md,
            "artifact_id": artifact_id,
        }
