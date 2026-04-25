from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger("proxy-provider")

RETRY_UNSUPPORTED_FIELDS = {
    "presence_penalty",
    "frequency_penalty",
    "top_p",
    "stop",
    "n",
    "logprobs",
    "top_logprobs",
    "user",
    "seed",
}


def remove_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: remove_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [remove_nulls(v) for v in value]
    return value


def prepare_upstream_body(body: dict[str, Any], model_uri: str) -> dict[str, Any]:
    prepared = remove_nulls(copy.deepcopy(body))
    prepared["model"] = model_uri
    return prepared


def remove_retry_unsupported_fields(body: dict[str, Any], request_id: str) -> tuple[dict[str, Any], list[str]]:
    retry_body = copy.deepcopy(body)
    removed: list[str] = []
    for field in RETRY_UNSUPPORTED_FIELDS:
        if field in retry_body:
            retry_body.pop(field, None)
            removed.append(field)

    if removed:
        logger.warning(
            "request_id=%s retrying after upstream 400 without fields=%s",
            request_id,
            ",".join(sorted(removed)),
        )
    return retry_body, sorted(removed)


def should_retry_400(body: dict[str, Any]) -> bool:
    return any(field in body for field in RETRY_UNSUPPORTED_FIELDS)


def extract_content(response_json: dict[str, Any]) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    return content if isinstance(content, str) else ""
