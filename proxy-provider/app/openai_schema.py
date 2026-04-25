from typing import Any

MODEL_ALIASES = ("yandex-direct", "yandex-private")


def model_list(extra_models: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = [
        {
            "id": "yandex-direct",
            "object": "model",
            "created": 0,
            "owned_by": "local-proxy",
        },
        {
            "id": "yandex-private",
            "object": "model",
            "created": 0,
            "owned_by": "local-proxy",
        },
    ]
    if extra_models:
        data.extend(extra_models)
    return {
        "object": "list",
        "data": data,
    }


def openai_error(message: str, error_type: str = "upstream_error", code: str | None = None) -> dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": None,
            "code": code,
        }
    }


def single_sse_chunk(content: str, model: str) -> bytes:
    payload = {
        "id": "chatcmpl-proxy-fallback",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None,
            }
        ],
    }
    import json

    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
