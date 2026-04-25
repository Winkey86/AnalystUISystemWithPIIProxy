from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class ProviderConfig(BaseModel):
    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    label: str = Field(default="", max_length=120)
    base_url: str = Field(min_length=8)
    api_key: str = Field(default="", max_length=4096)
    model: str = Field(min_length=1, max_length=512)
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    def public_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["api_key_set"] = bool(self.api_key)
        data.pop("api_key", None)
        return data


def _provider_path() -> Path:
    path = Path(settings.provider_config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_sync() -> list[ProviderConfig]:
    path = _provider_path()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return []
    return [ProviderConfig.model_validate(item) for item in raw]


def _save_sync(providers: list[ProviderConfig]) -> None:
    path = _provider_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump([provider.model_dump() for provider in providers], handle, ensure_ascii=False, indent=2)


async def list_extra_providers() -> list[ProviderConfig]:
    return await asyncio.to_thread(_load_sync)


async def public_providers() -> list[dict[str, Any]]:
    providers = await list_extra_providers()
    return [provider.public_dict() for provider in providers]


async def get_extra_provider(provider_id: str) -> ProviderConfig | None:
    providers = await list_extra_providers()
    for provider in providers:
        if provider.id == provider_id and provider.enabled:
            return provider
    return None


async def upsert_provider(config: ProviderConfig) -> dict[str, Any]:
    providers = await list_extra_providers()
    next_providers: list[ProviderConfig] = []
    replaced = False
    for provider in providers:
        if provider.id == config.id:
            next_providers.append(config)
            replaced = True
        else:
            next_providers.append(provider)
    if not replaced:
        next_providers.append(config)
    await asyncio.to_thread(_save_sync, next_providers)
    return config.public_dict()
