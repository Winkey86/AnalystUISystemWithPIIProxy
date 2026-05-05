from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("analyst-mcp.agent")


class BaseAgentTool:
    """Базовый класс для agent-tool: вызывает LLM через proxy-provider."""

    system_prompt: str = "Ты — специализированный аналитический агент."

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
    ) -> str:
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                *messages,
            ],
            "stream": False,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.proxy_provider_url}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.proxy_provider_api_key}"},
            )
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_llm_sync(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
    ) -> str:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self._call_llm(messages, temperature))
                return future.result(timeout=settings.llm_timeout_seconds + 10)
        return loop.run_until_complete(self._call_llm(messages, temperature))

    def _parse_json_response(self, text: str) -> Any:
        """Извлечь JSON из ответа LLM (может быть обёрнут в ```json ... ```)."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Убрать первую и последнюю строку с ```
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(inner)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_response": text}
