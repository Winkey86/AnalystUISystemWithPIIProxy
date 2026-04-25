from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi.responses import JSONResponse

from app.config import Settings
from app.openai_schema import openai_error
from app.proxy_client import remove_retry_unsupported_fields, should_retry_400

logger = logging.getLogger("proxy-provider")


class UpstreamError(Exception):
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(str(payload))


def yandex_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.yandex_api_key}",
    }
    if settings.yandex_folder_id:
        headers["OpenAI-Project"] = settings.yandex_folder_id
    return headers


def upstream_url(settings: Settings) -> str:
    return f"{settings.yandex_base_url}/chat/completions"


async def post_json(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
    request_id: str,
) -> tuple[int, Any, dict[str, str]]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise UpstreamError(504, openai_error("Upstream request timed out", "timeout_error")) from exc
        except httpx.RequestError as exc:
            raise UpstreamError(502, openai_error(f"Upstream request failed: {exc.__class__.__name__}", "connection_error")) from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            payload = openai_error("Upstream returned invalid JSON", "invalid_upstream_response")
    else:
        payload = response.text

    logger.debug("request_id=%s upstream_status=%s", request_id, response.status_code)
    return response.status_code, payload, dict(response.headers)


async def post_json_with_retry(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
    request_id: str,
) -> tuple[int, Any, dict[str, str]]:
    status, payload, response_headers = await post_json(url, headers, body, timeout, request_id)
    if status == 400 and should_retry_400(body):
        retry_body, removed = remove_retry_unsupported_fields(body, request_id)
        if removed:
            status, payload, response_headers = await post_json(url, headers, retry_body, timeout, request_id)
    return status, payload, response_headers


def upstream_json_response(status: int, payload: Any) -> JSONResponse:
    if status in (401, 403):
        return JSONResponse(
            status_code=status,
            content=openai_error("Yandex AI Studio authorization failed. Check YANDEX_API_KEY and folder access.", "auth_error"),
        )
    if isinstance(payload, dict):
        return JSONResponse(status_code=status, content=payload)
    return JSONResponse(status_code=status, content=openai_error(str(payload), "upstream_error"))
