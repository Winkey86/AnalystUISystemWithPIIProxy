from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from app.admin_ui import ADMIN_HTML
from app.audit import insert_request_log, list_request_logs
from app.config import settings
from app.openai_schema import MODEL_ALIASES, model_list, openai_error, single_sse_chunk
from app.providers import ProviderConfig, get_extra_provider, public_providers, upsert_provider
from app.proxy_client import extract_content, prepare_upstream_body
from app.yandex_client import post_json_with_retry, upstream_json_response, upstream_url, yandex_headers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("proxy-provider")

app = FastAPI(title="Open WebUI Yandex Proxy Provider")


def _bearer_value(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


async def require_public_auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.require_proxy_auth:
        return
    if _bearer_value(authorization) != settings.proxy_provider_api_key:
        return _raise_json(401, "Invalid proxy provider API key", "auth_error")


async def require_internal_auth(authorization: str | None = Header(default=None)) -> None:
    if _bearer_value(authorization) != settings.anon_internal_api_key:
        return _raise_json(401, "Invalid internal proxy API key", "auth_error")


async def require_admin_auth(x_admin_key: str | None = Header(default=None)) -> None:
    if not settings.admin_ui_enabled:
        return _raise_json(404, "Admin UI is disabled", "not_found")
    if x_admin_key != settings.effective_admin_ui_api_key:
        return _raise_json(401, "Invalid admin UI key", "auth_error")


def _raise_json(status: int, message: str, error_type: str) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=status, detail=openai_error(message, error_type)["error"])


def _route_for_model(model_alias: str) -> bool:
    if model_alias == "yandex-private":
        return True
    if model_alias == "yandex-direct":
        return False
    if settings.force_private_for_yandex_model_uri and (
        model_alias == settings.yandex_model_uri or model_alias.startswith("gpt://")
    ):
        return True
    return settings.privacy_default_enabled


def _latency_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def _yandex_config_error() -> JSONResponse | None:
    missing = []
    if not settings.yandex_api_key:
        missing.append("YANDEX_API_KEY")
    if not settings.yandex_folder_id:
        missing.append("YANDEX_FOLDER_ID")
    if not missing:
        return None

    return JSONResponse(
        status_code=503,
        content=openai_error(
            f"Yandex upstream is not configured: set {', '.join(missing)} in .env and recreate proxy-provider",
            "configuration_error",
        ),
    )


def _log_request(
    request_id: str,
    route: str,
    model_alias: str,
    stream: bool,
    start: float,
    status: int | None = None,
) -> None:
    logger.info(
        "request_id=%s route=%s model_alias=%s stream=%s status=%s latency_ms=%.1f",
        request_id,
        route,
        model_alias,
        stream,
        status if status is not None else "-",
        (time.perf_counter() - start) * 1000,
    )


def _private_anon_hop_summary(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    return {
        "hop": "anon-proxy",
        "note": (
            "This private-route payload is sent only to the local anonymizer. "
            "Use the matching route=internal-yandex row with the same request_id "
            "to inspect the actual payload sent to Yandex."
        ),
        "model": body.get("model"),
        "stream": body.get("stream"),
        "message_count": len(messages) if isinstance(messages, list) else None,
    }


def _audit_upstream_payload(route: str, body: dict[str, Any]) -> Any:
    if route == "private":
        return _private_anon_hop_summary(body)
    return body


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and {"message", "type"}.issubset(detail.keys()):
        return JSONResponse(status_code=exc.status_code, content={"error": detail})
    return JSONResponse(status_code=exc.status_code, content=openai_error(str(detail), "request_error"))


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled proxy-provider error")
    return JSONResponse(status_code=500, content=openai_error("Internal proxy-provider error", "internal_error"))


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "privacy_default_enabled": settings.privacy_default_enabled,
        "force_private_for_yandex_model_uri": settings.force_private_for_yandex_model_uri,
        "yandex_base_url": settings.yandex_base_url,
        "anon_proxy_url": settings.anon_proxy_url,
        "default_model": settings.yandex_model_uri,
        "yandex_configured": bool(settings.yandex_api_key and settings.yandex_folder_id),
        "audit_log_content": settings.audit_log_content,
        "admin_ui_enabled": settings.admin_ui_enabled,
    }


@app.get("/v1/models")
async def models(_: None = Depends(require_public_auth)) -> dict[str, Any]:
    extra = [
        {"id": provider["id"], "object": "model", "created": 0, "owned_by": "configured-provider"}
        for provider in await public_providers()
        if provider.get("enabled")
    ]
    return model_list(extra)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page() -> HTMLResponse:
    if not settings.admin_ui_enabled:
        return HTMLResponse("Admin UI is disabled", status_code=404)
    return HTMLResponse(ADMIN_HTML)


@app.get("/admin/api/logs")
async def admin_logs(limit: int = 100, _: None = Depends(require_admin_auth)) -> dict[str, Any]:
    return {"logs": await list_request_logs(limit)}


@app.get("/admin/api/providers")
async def admin_providers(_: None = Depends(require_admin_auth)) -> dict[str, Any]:
    return {"providers": await public_providers()}


@app.post("/admin/api/providers")
async def admin_upsert_provider(provider: ProviderConfig, _: None = Depends(require_admin_auth)) -> dict[str, Any]:
    saved = await upsert_provider(provider)
    return {"provider": saved}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, _: None = Depends(require_public_auth)) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content=openai_error("Invalid JSON body", "invalid_request_error"))

    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content=openai_error("JSON body must be an object", "invalid_request_error"))

    model_alias = str(body.get("model") or "")
    stream = bool(body.get("stream") is True) and not settings.force_non_stream
    configured_provider = await get_extra_provider(model_alias)
    privacy_enabled = False if configured_provider else _route_for_model(model_alias)
    route = "configured-direct" if configured_provider else ("private" if privacy_enabled else "direct")
    provider_name = configured_provider.id if configured_provider else "yandex"

    if settings.debug_log_content:
        logger.warning("request_id=%s DEBUG_LOG_CONTENT body=%s", request_id, json.dumps(body, ensure_ascii=False))

    if not configured_provider and (config_error := _yandex_config_error()):
        _log_request(request_id, route, model_alias, stream, start, config_error.status_code)
        await insert_request_log(
            request_id=request_id,
            provider=provider_name,
            route=route,
            model_alias=model_alias,
            stream=stream,
            status=config_error.status_code,
            latency_ms=_latency_ms(start),
            incoming_json=body,
            error="Yandex upstream is not configured",
        )
        return config_error

    upstream_model = configured_provider.model if configured_provider else settings.yandex_model_uri
    upstream_body = prepare_upstream_body(body, upstream_model)

    if configured_provider:
        target_url = f"{configured_provider.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {configured_provider.api_key}",
            "X-Request-Id": request_id,
        }
    elif privacy_enabled:
        target_url = f"{settings.anon_proxy_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.anon_internal_api_key}",
            "X-Request-Id": request_id,
            "X-Conversation-Id": request.headers.get("x-conversation-id", request_id),
        }
    else:
        target_url = upstream_url(settings)
        headers = yandex_headers(settings)

    if stream:
        return await _stream_response(
            target_url=target_url,
            headers=headers,
            body=upstream_body,
            request_id=request_id,
            route=route,
            model_alias=model_alias,
            start=start,
            allow_non_stream_fallback=privacy_enabled,
            provider=provider_name,
            incoming_body=body,
        )

    response = await _json_completion(target_url, headers, upstream_body, request_id)
    _log_request(request_id, route, model_alias, False, start, response.status_code)
    response_payload: Any
    try:
        response_payload = json.loads(response.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        response_payload = response.body.decode("utf-8", errors="replace")
    await insert_request_log(
        request_id=request_id,
        provider=provider_name,
        route=route,
        model_alias=model_alias,
        stream=False,
        status=response.status_code,
        latency_ms=_latency_ms(start),
        incoming_json=body,
        upstream_json=_audit_upstream_payload(route, upstream_body),
        response_json=response_payload,
    )
    return response


@app.post("/_internal/yandex/v1/chat/completions")
async def internal_yandex_forwarder(request: Request, _: None = Depends(require_internal_auth)) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content=openai_error("Invalid JSON body", "invalid_request_error"))
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content=openai_error("JSON body must be an object", "invalid_request_error"))

    stream = bool(body.get("stream") is True) and not settings.force_non_stream
    if config_error := _yandex_config_error():
        _log_request(request_id, "internal-yandex", str(body.get("model") or ""), stream, start, config_error.status_code)
        await insert_request_log(
            request_id=request_id,
            provider="yandex",
            route="internal-yandex",
            model_alias=str(body.get("model") or ""),
            stream=stream,
            status=config_error.status_code,
            latency_ms=_latency_ms(start),
            incoming_json=body,
            error="Yandex upstream is not configured",
        )
        return config_error

    if stream:
        return await _stream_response(
            target_url=upstream_url(settings),
            headers=yandex_headers(settings),
            body=body,
            request_id=request_id,
            route="internal-yandex",
            model_alias=str(body.get("model") or ""),
            start=start,
            allow_non_stream_fallback=False,
            provider="yandex",
            incoming_body=body,
        )

    response = await _json_completion(upstream_url(settings), yandex_headers(settings), body, request_id)
    _log_request(request_id, "internal-yandex", str(body.get("model") or ""), False, start, response.status_code)
    try:
        response_payload = json.loads(response.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        response_payload = response.body.decode("utf-8", errors="replace")
    await insert_request_log(
        request_id=request_id,
        provider="yandex",
        route="internal-yandex",
        model_alias=str(body.get("model") or ""),
        stream=False,
        status=response.status_code,
        latency_ms=_latency_ms(start),
        incoming_json=body,
        upstream_json=body,
        response_json=response_payload,
    )
    return response


async def _json_completion(
    target_url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    request_id: str,
) -> JSONResponse:
    status, payload, _ = await post_json_with_retry(
        target_url,
        headers,
        body,
        settings.upstream_timeout_seconds,
        request_id,
    )
    return upstream_json_response(status, payload)


async def _stream_response(
    target_url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    request_id: str,
    route: str,
    model_alias: str,
    start: float,
    allow_non_stream_fallback: bool,
    provider: str,
    incoming_body: dict[str, Any],
) -> Response:
    client = httpx.AsyncClient(timeout=settings.upstream_timeout_seconds)
    request = client.build_request("POST", target_url, headers=headers, json=body)
    try:
        upstream = await client.send(request, stream=True)
    except httpx.TimeoutException:
        await client.aclose()
        _log_request(request_id, route, model_alias, True, start, 504)
        await insert_request_log(
            request_id=request_id,
            provider=provider,
            route=route,
            model_alias=model_alias,
            stream=True,
            status=504,
            latency_ms=_latency_ms(start),
            incoming_json=incoming_body,
            upstream_json=_audit_upstream_payload(route, body),
            error="Upstream request timed out",
        )
        return JSONResponse(status_code=504, content=openai_error("Upstream request timed out", "timeout_error"))
    except httpx.RequestError as exc:
        await client.aclose()
        if allow_non_stream_fallback:
            logger.warning(
                "request_id=%s route=%s stream failed with %s; retrying as non-streaming SSE fallback",
                request_id,
                route,
                exc.__class__.__name__,
            )
            return await _fallback_non_stream_sse(
                target_url,
                headers,
                body,
                request_id,
                route,
                model_alias,
                start,
                provider,
                incoming_body,
            )
        _log_request(request_id, route, model_alias, True, start, 502)
        await insert_request_log(
            request_id=request_id,
            provider=provider,
            route=route,
            model_alias=model_alias,
            stream=True,
            status=502,
            latency_ms=_latency_ms(start),
            incoming_json=incoming_body,
            upstream_json=_audit_upstream_payload(route, body),
            error=f"Upstream stream request failed: {exc.__class__.__name__}",
        )
        return JSONResponse(
            status_code=502,
            content=openai_error(f"Upstream stream request failed: {exc.__class__.__name__}", "connection_error"),
        )

    if upstream.status_code >= 400:
        payload_text = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        if allow_non_stream_fallback:
            logger.warning(
                "request_id=%s route=%s stream returned status=%s; retrying as non-streaming SSE fallback",
                request_id,
                route,
                upstream.status_code,
            )
            return await _fallback_non_stream_sse(
                target_url,
                headers,
                body,
                request_id,
                route,
                model_alias,
                start,
                provider,
                incoming_body,
            )
        _log_request(request_id, route, model_alias, True, start, upstream.status_code)
        try:
            payload = json.loads(payload_text.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = openai_error(payload_text.decode("utf-8", errors="replace"), "upstream_error")
        await insert_request_log(
            request_id=request_id,
            provider=provider,
            route=route,
            model_alias=model_alias,
            stream=True,
            status=upstream.status_code,
            latency_ms=_latency_ms(start),
            incoming_json=incoming_body,
            upstream_json=_audit_upstream_payload(route, body),
            response_json=payload,
        )
        return upstream_json_response(upstream.status_code, payload)

    captured = bytearray()
    capture_limit = 65536

    async def iter_bytes() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                if len(captured) < capture_limit:
                    captured.extend(chunk[: capture_limit - len(captured)])
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()
            _log_request(request_id, route, model_alias, True, start, upstream.status_code)
            import anyio
            with anyio.CancelScope(shield=True):
                await insert_request_log(
                    request_id=request_id,
                    provider=provider,
                    route=route,
                    model_alias=model_alias,
                    stream=True,
                    status=upstream.status_code,
                    latency_ms=_latency_ms(start),
                    incoming_json=incoming_body,
                    upstream_json=_audit_upstream_payload(route, body),
                    response_json={
                        "stream_sample": captured.decode("utf-8", errors="replace"),
                        "truncated": len(captured) >= capture_limit,
                    },
                )

    return StreamingResponse(
        iter_bytes(),
        status_code=upstream.status_code,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Request-Id": request_id},
    )


async def _fallback_non_stream_sse(
    target_url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    request_id: str,
    route: str,
    model_alias: str,
    start: float,
    provider: str,
    incoming_body: dict[str, Any],
) -> StreamingResponse:
    fallback_body = {**body, "stream": False}
    response = await _json_completion(target_url, headers, fallback_body, request_id)
    if response.status_code >= 400:
        try:
            error_payload: Any = json.loads(response.body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            error_payload = response.body.decode("utf-8", errors="replace")

        async def error_iter() -> AsyncIterator[bytes]:
            try:
                yield response.body
            finally:
                import anyio
                with anyio.CancelScope(shield=True):
                    await insert_request_log(
                        request_id=request_id,
                        provider=provider,
                        route=route,
                        model_alias=model_alias,
                        stream=True,
                        status=response.status_code,
                        latency_ms=_latency_ms(start),
                        incoming_json=incoming_body,
                        upstream_json=_audit_upstream_payload(route, fallback_body),
                        response_json=error_payload,
                        error="non-stream fallback failed",
                    )

        return StreamingResponse(error_iter(), status_code=response.status_code, media_type="application/json")

    payload = json.loads(response.body.decode("utf-8"))
    content = extract_content(payload)

    async def iter_fallback() -> AsyncIterator[bytes]:
        try:
            yield single_sse_chunk(content, settings.yandex_model_uri)
            yield b"data: [DONE]\n\n"
        finally:
            _log_request(request_id, route, model_alias, True, start, 200)
            import anyio
            with anyio.CancelScope(shield=True):
                await insert_request_log(
                    request_id=request_id,
                    provider=provider,
                    route=route,
                    model_alias=model_alias,
                    stream=True,
                    status=200,
                    latency_ms=_latency_ms(start),
                    incoming_json=incoming_body,
                    upstream_json=_audit_upstream_payload(route, fallback_body),
                    response_json=payload,
                )

    return StreamingResponse(iter_fallback(), status_code=200, media_type="text/event-stream")
