"""The shared runner: structured output, validation, retry once, then mock fallback.

Providers only produce raw text; this is where every response gets validated
against the task's pydantic model, where the response store is consulted, and
where provenance (`mock | llm | fallback`) is decided.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from overheard.llm.cache import ResponseStore
from overheard.llm.mock import MockProvider
from overheard.llm.provider import LLMProvider, Task, input_hash


@dataclass
class LLMResult:
    data: BaseModel
    provenance: str  # mock | llm | fallback
    model: str
    key: str


def _try_parse(task: Task, raw: str | None):
    if raw is None:
        return None
    try:
        return task.output_model.model_validate_json(raw)
    except ValidationError:
        return None


async def run_task(
    provider: LLMProvider,
    task: Task,
    model: str,
    store: ResponseStore | None = None,
    read_cache: bool = True,
    write: bool = False,
    provenance: str = "llm",
) -> LLMResult:
    """Run `task` on `provider`. Cache hit first, then the provider, then one
    retry with the error appended, then the from-truth mock marked `fallback`. The model is the task's own when
    per-task models are set (OVERHEARD_LLM_TASK_MODELS), else the one given."""
    from overheard.llm.provider import model_for
    model = model_for(task.name, model)
    key = input_hash(task, model)
    if store is not None and read_cache:
        cached = store.get(task.name, key, model)
        if cached is not None:
            data = _try_parse(task, cached)
            if data is not None:
                return LLMResult(data, provenance, model, key)

    raw = await provider.complete(task, model)
    data = _try_parse(task, raw)
    if data is None and raw is not None:
        # one retry, with the error from the first attempt appended
        prompt = task.model_copy(
            update={
                "user": (
                    f"{task.user}\n\nYour previous reply could not be parsed: {raw}\n"
                    "Reply again with only the JSON object."
                )
            }
        )
        raw = await provider.complete(prompt, model)
        data = _try_parse(task, raw)
    if data is not None:
        if write and store is not None:
            store.put(task.name, key, model, raw)
        return LLMResult(data, provenance, model, key)

    # Fallback: the from-truth mock keeps every mode working; it is marked as such.
    mock_raw = await MockProvider().complete(task, model)
    return LLMResult(task.output_model.model_validate_json(mock_raw), "fallback", model, key)
