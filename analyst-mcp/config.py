from __future__ import annotations

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM upstream (proxy-provider)
    proxy_provider_url: str = "http://proxy-provider:8081"
    proxy_provider_api_key: str = "local-dev-key"
    llm_model: str = "yandex-private"
    llm_timeout_seconds: float = Field(default=180.0, ge=1.0)

    # Anon proxy (для Data Anonymizer)
    anon_proxy_url: str = "http://anon-proxy:8000"

    # Хранилище данных
    data_dir: str = "/data"

    # MCP-сервер
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8082

    # Аудит-лог шагов метакоординации
    audit_log_path: str = "/data/mcp_audit.jsonl"
    audit_enabled: bool = True

    # Лимиты
    max_rows_preview: int = Field(default=100, ge=1)
    max_rows_result: int = Field(default=500, ge=1)
    max_rows_load: int = Field(default=100_000, ge=1)

    @cached_property
    def uploads_dir(self) -> str:
        return f"{self.data_dir}/uploads"

    @cached_property
    def artifacts_dir(self) -> str:
        return f"{self.data_dir}/artifacts"

    @cached_property
    def plots_dir(self) -> str:
        return f"{self.data_dir}/plots"

    @cached_property
    def metadata_dir(self) -> str:
        return f"{self.data_dir}/metadata"


settings = Settings()
