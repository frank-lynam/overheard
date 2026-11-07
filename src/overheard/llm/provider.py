"""The LLM seam: one Protocol, four modes, one shared runner.

Every provider implements `provider(name, model)`; the runner in `run.py`
handles structured output, validation, retry and fallback so providers only
have to produce raw text. Mode is `OVERHEARD_LLM_MODE` = mock | live | record
| replay. Mock needs no network and no fixtures: it builds output from the
message's ground-truth labels with a seeded share of realistic mistakes.
"""

import hashlib
import json
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from overheard.config import Settings
from overheard.llm.cache import ResponseStore

Provenance = Literal["mock", "llm", "fallback", "human"]


class Task(BaseModel):
    """One LLM task: a system prompt, few-shot examples, a strict output model."""

    name: str
    description: str
    system: str
    user: str
    output_model: type[BaseModel]
    examples: list[dict] = []
    # Ground-truth labels and other in-band context, for the mock and for scoring.
    # Never sent to a live host (it is not part of the prompt).
    context: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(self, task: Task, model: str) -> str:
        """Return the model's raw text for `task`."""
        ...


def input_hash(task: Task, model: str) -> str:
    """Stable key part: the task's full text plus the model, sha256-truncated."""
    payload = {"system": task.system, "user": task.user, "model": model, "examples": task.examples, "context": task.context}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]


def build_provider(settings: Settings, store: ResponseStore) -> LLMProvider:
    from overheard.llm.mock import MockProvider
    from overheard.llm.openai_compat import OpenAICompatProvider
    from overheard.llm.replay import ReplayProvider

    TASK_MODELS.clear()
    if settings.llm_mode == "mock":       # the mock is one model, whatever the tasks would use live
        return MockProvider()
    TASK_MODELS.update(settings.llm_task_models)
    if settings.llm_mode == "replay":
        return ReplayProvider(settings, store)
    if settings.llm_provider in ("anthropic", "bedrock"):
        from overheard.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(settings, bedrock=settings.llm_provider == "bedrock")
    return OpenAICompatProvider(settings, store, record=settings.llm_mode == "record")


# Per-task models (OVERHEARD_LLM_TASK_MODELS), set from the settings when the provider is built; the runner looks
# each task up here, so every caller keeps passing the one default model.
TASK_MODELS: dict[str, str] = {}


def model_for(task_name: str, model: str) -> str:
    return TASK_MODELS.get(task_name, model)
