from __future__ import annotations

import json
from typing import Any, Callable

import jsonschema


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def json_parse(raw: str) -> dict[str, Any]:
        """Разобрать JSON-строку в объект.

        Args:
            raw: JSON-строка.

        Returns:
            {"parsed": object} или {"error": str}
        """
        try:
            return {"parsed": json.loads(raw)}
        except json.JSONDecodeError as exc:
            return {"error": str(exc)}

    @mcp.tool()
    @audited
    def json_validate(raw: str, schema: dict) -> dict[str, Any]:
        """Валидировать JSON-строку против JSON Schema.

        Args:
            raw: JSON-строка с данными.
            schema: JSON Schema (dict).

        Returns:
            {"valid": bool, "errors": list[str]}
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {"valid": False, "errors": [f"JSON parse error: {exc}"]}

        validator = jsonschema.Draft7Validator(schema)
        errors = [e.message for e in validator.iter_errors(data)]
        return {"valid": len(errors) == 0, "errors": errors}
