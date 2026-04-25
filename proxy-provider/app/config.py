from functools import cached_property

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    proxy_provider_api_key: str = "local-dev-key"
    require_proxy_auth: bool = False
    privacy_default_enabled: bool = True
    force_private_for_yandex_model_uri: bool = True

    yandex_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model_id: str = "qwen3-235b-a22b-fp8"

    anon_proxy_url: str = "http://anon-proxy:8000"
    anon_internal_api_key: str = "local-anon-internal-key"

    force_non_stream: bool = False
    debug_log_content: bool = False
    audit_log_content: bool = False
    audit_db_path: str = "/data/audit.db"
    audit_retention: int = Field(default=500, ge=10)
    admin_ui_enabled: bool = True
    admin_ui_api_key: str = ""
    provider_config_path: str = "/data/providers.json"
    upstream_timeout_seconds: float = Field(default=120.0, ge=1.0)

    @field_validator("yandex_base_url", "anon_proxy_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @cached_property
    def yandex_model_uri(self) -> str:
        return f"gpt://{self.yandex_folder_id}/{self.yandex_model_id}/latest"

    @cached_property
    def effective_admin_ui_api_key(self) -> str:
        return self.admin_ui_api_key or self.proxy_provider_api_key


settings = Settings()
