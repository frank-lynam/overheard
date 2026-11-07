"""Settings, from OVERHEARD_* environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVERHEARD_")

    llm_mode: Literal["mock", "live", "record", "replay"] = "mock"
    # which host serves live and record: any OpenAI-compatible host, Claude's API, or Claude on Amazon Bedrock
    llm_provider: Literal["openai_compat", "anthropic", "bedrock"] = "openai_compat"
    aws_region: str | None = None          # Bedrock's region, e.g. us-gov-west-1 (OVERHEARD_AWS_REGION)
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"   # Claude's effort (anthropic, bedrock)
    # per-task models, as JSON: {"junk_classify": "<a small model>", "team_propose": "<a large one>"}; the rest
    # use llm_model. The model is part of each stored answer's key and of its provenance.
    llm_task_models: dict[str, str] = {}
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout: float = 60.0
    llm_responses_path: Path = Path("overheard_responses")  # the JSON response store (one per (task, input, model))
    db_path: Path = Path("overheard.db")
    # Where tickets go: a hearthboard (its URL and Overheard's agent token there), else a local mock board
    workflow_url: str | None = None
    workflow_token: SecretStr | None = None
    seed: int = 2026
    host: str = "127.0.0.1"
    port: int = 8000
    labor_rate: float = 55.0  # fully-loaded dollars per agent-hour (Mode 3 cost model)
