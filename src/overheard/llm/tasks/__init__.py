"""Task modules: one per LLM job.

Each module has a system prompt, few-shot examples, a strict pydantic output
model and a `build(...)` that produces the Task from a message. The message's
ground-truth labels travel in `Task.context` (JSON) so the mock and the
scorers can use them; they are not part of the prompt a live host sees.
"""

import json

from overheard.data.models import Voicemail


def _truth_context(v: Voicemail) -> str:
    return json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False)


def _user(v: Voicemail, ask: str) -> str:
    lang = "" if v.lang == "en" else f" (The caller is speaking {v.lang}.)"
    return f"Voicemail transcript{lang}:\n{v.script}\n\n{ask}"


#: every task, by name — the pipeline and the tests both iterate this
TASKS: dict[str, type] = {}


def _register(cls: type) -> type:
    TASKS[cls.name] = cls
    return cls


# Importing this package imports every task module so `_register` runs.
from overheard.llm.tasks import (  # noqa: E402,F401
    draft_reply,
    extraction,
    incident,
    intent_urgency,
    junk_classify,
    problem_classify,
    resolution,
    routing,
    sentiment,
    summary,
    team_propose,
    translation,
)
