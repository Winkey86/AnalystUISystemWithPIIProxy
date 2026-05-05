from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from audit import log_tool_call, read_audit_log
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("analyst-mcp")

mcp = FastMCP("analyst-mcp")


async def _health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "analyst-mcp"})


mcp.custom_route("/health", _health_endpoint, methods=["GET"])


def _audited(fn: Callable) -> Callable:
    """Декоратор: логирует каждый вызов инструмента в audit.jsonl."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        error: str | None = None
        result: Any = None
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            log_tool_call(
                tool_name=fn.__name__,
                args_keys=list(kwargs.keys()),
                result_type=type(result).__name__ if result is not None else "None",
                elapsed_ms=elapsed,
                error=error,
            )

    return wrapper


# ── Регистрация direct tools ────────────────────────────────────────────────

from direct_tools import (  # noqa: E402
    artifacts,
    excel_tools,
    formatter,
    json_tools,
    metadata,
    preview,
    registry,
    sql_preview,
)

registry.register(mcp, _audited)
metadata.register(mcp, _audited)
artifacts.register(mcp, _audited)
preview.register(mcp, _audited)
json_tools.register(mcp, _audited)
excel_tools.register(mcp, _audited)
sql_preview.register(mcp, _audited)
formatter.register(mcp, _audited)

# ── Регистрация agent-tools ─────────────────────────────────────────────────

from agent_tools import (  # noqa: E402
    data_quality_agent,
    data_source_agent,
    python_analytics_agent,
    reporting_agent,
    sql_analysis_agent,
    transformation_agent,
    visualization_agent,
)

data_source_agent.register(mcp, _audited)
data_quality_agent.register(mcp, _audited)
transformation_agent.register(mcp, _audited)
sql_analysis_agent.register(mcp, _audited)
python_analytics_agent.register(mcp, _audited)
visualization_agent.register(mcp, _audited)
reporting_agent.register(mcp, _audited)


# ── Служебные эндпоинты ─────────────────────────────────────────────────────

@mcp.tool()
def get_audit_log(limit: int = 100) -> dict[str, Any]:
    """Последние N записей лога шагов метакоординации."""
    return {"records": read_audit_log(limit)}


# ── Запуск ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting analyst-mcp on %s:%s", settings.mcp_host, settings.mcp_port)
    mcp.run(transport="sse", host=settings.mcp_host, port=settings.mcp_port)
