"""ReplayProvider: the response store only, no network.

Same day, same model, same store: identical answers. A miss is not an error
for the runner (the from-truth mock fallback is used and marked `fallback`),
but the miss is logged so you can see which fixtures are missing before the
offline dry run.
"""

import logging

from overheard.config import Settings
from overheard.llm.cache import ResponseStore
from overheard.llm.provider import Task, input_hash

log = logging.getLogger("overheard.llm")


class ReplayProvider:
    name = "replay"

    def __init__(self, settings: Settings, store: ResponseStore) -> None:
        self.model = settings.llm_model or "gpt-4o-mini"
        self.store = store

    async def complete(self, task: Task, model: str) -> str | None:
        m = model or self.model
        out = self.store.get(task.name, input_hash(task, m), m)
        if out is None:
            log.warning("replay miss: %s / %s", task.name, m)
        return out
