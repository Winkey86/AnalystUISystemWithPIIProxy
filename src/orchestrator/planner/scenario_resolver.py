"""Rules-based scenario resolver."""

from __future__ import annotations

ARTIFACT_KEYWORDS = (
    "график",
    "диаграм",
    "документ",
    "картинк",
    "изображени",
)


def resolve_scenario_id(user_message: str, attachments: list[str] | None = None) -> str:
    if attachments:
        return "file_analysis"

    normalized = normalize_text(user_message)
    if requests_artifact_first(normalized):
        return "artifact_first_response"

    return "factual_qa"


def normalize_text(text: str) -> str:
    return text.strip().lower()


def requests_artifact_first(text: str) -> bool:
    return any(keyword in text for keyword in ARTIFACT_KEYWORDS)
