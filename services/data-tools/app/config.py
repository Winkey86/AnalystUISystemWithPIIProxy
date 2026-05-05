from pathlib import Path
import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    data_input_dir: Path = Field(default=Path("/data/input"))
    artifact_root: Path = Field(default=Path("/data/artifacts"))
    max_preview_rows: int = Field(default=50, ge=1)
    max_query_rows: int = Field(default=1000, ge=1)
    query_timeout_seconds: int = Field(default=10, ge=1)
    max_file_size_mb: int = Field(default=100, ge=1)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def get_settings() -> Settings:
    return Settings(
        data_input_dir=Path(os.getenv("DATA_INPUT_DIR", "/data/input")).resolve(),
        artifact_root=Path(os.getenv("ARTIFACT_ROOT", "/data/artifacts")).resolve(),
        max_preview_rows=_env_int("MAX_PREVIEW_ROWS", 50),
        max_query_rows=_env_int("MAX_QUERY_ROWS", 1000),
        query_timeout_seconds=_env_int("QUERY_TIMEOUT_SECONDS", 10),
        max_file_size_mb=_env_int("MAX_FILE_SIZE_MB", 100),
    )
