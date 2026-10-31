"""Settings, from OVERHEARD_* environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVERHEARD_")

    llm_mode: Literal["mock", "live", "record", "replay"] = "mock"
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout: float = 60.0
    db_path: Path = Path("overheard.db")
    seed: int = 2026
    host: str = "127.0.0.1"
    port: int = 8000
