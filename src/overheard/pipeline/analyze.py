"""The analysis pipeline: every task on a message, one bundle per message.

Runs the whole task set (seven) on a voicemail through the shared runner,
persists each result with its provenance (`mock | llm | fallback`), and
assembles one bundle that the API and the mode-1 front end read. Re-running
while the provider is the same is cheap: every task is read from the response
store or the database first, so nothing is asked twice.
"""

import json
import sqlite3
import threading
from dataclasses import dataclass

from overheard.data.models import Voicemail
from overheard.llm import ResponseStore, run_task
from overheard.llm.provider import LLMProvider
from overheard.llm.tasks import TASKS
from overheard.llm.tasks.draft_reply import DraftOut
from overheard.llm.tasks.extraction import ExtractionOut
from overheard.llm.tasks.intent_urgency import IntentOut
from overheard.llm.tasks.routing import RoutingOut
from overheard.llm.tasks.sentiment import SentimentOut
from overheard.llm.tasks.summary import SummaryOut
from overheard.llm.tasks.translation import TranslationOut


@dataclass
class AnalysisDeps:
    con: sqlite3.Connection
    store: ResponseStore
    provider: LLMProvider
    model: str
    lock: threading.Lock = threading.Lock()  # the connection is shared; one analysis at a time
    cache: dict[str, dict] | None = None  # message id -> bundle, so re-runs never touch the db


async def analyze(vm: Voicemail, deps: AnalysisDeps, force: bool = False) -> dict:
    """Run every task on `vm`, persist the results, and return the bundle:
    `{task: {data, provenance, model}}` plus `id`, `words` and `tasks`."""
    if not force and deps.cache is not None and vm.id in deps.cache:
        return deps.cache[vm.id]
    async with _anyio_lock(deps.lock):
        return await _analyze_locked(vm, deps, force)


#: the tasks that run per message; the mode-2 cluster tasks (incident, resolution)
#: have their own pipeline and are driven by the API, not per message here
_PER_MESSAGE = ("summary", "extraction", "intent_urgency", "routing", "translation", "sentiment", "draft_reply")


async def _analyze_locked(vm: Voicemail, deps: AnalysisDeps, force: bool = False) -> dict:
    bundle: dict = {"id": vm.id, "words": len(vm.script.split())}
    for name in _PER_MESSAGE:
        task_cls = TASKS[name]
        if not force:
            row = deps.con.execute(
                "SELECT data, provenance, model FROM analysis WHERE voicemail = ? AND task = ?", (vm.id, name)
            ).fetchone()
            if row is not None:
                bundle[name] = {"data": json.loads(row["data"]), "provenance": row["provenance"], "model": row["model"]}
                continue
        task = task_cls.build(vm)
        result = await run_task(deps.provider, task, deps.model, deps.store, write=False)
        deps.con.execute(
            "INSERT OR REPLACE INTO analysis (voicemail, task, model, data, provenance) VALUES (?, ?, ?, ?, ?)",
            (vm.id, name, result.model, result.data.model_dump_json(), result.provenance),
        )
        bundle[name] = {"data": result.data.model_dump(mode="json"), "provenance": result.provenance, "model": result.model}
    deps.con.commit()
    if deps.cache is not None:
        deps.cache[vm.id] = bundle
    return bundle


def _anyio_lock(lock: threading.Lock):
    """`async with` over a threading lock: the body is synchronous (the run-task steps
    are mocked locally), so this is only there to keep the lock's surface small."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _ctx():
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    return _ctx()


def analyze_sync(vm: Voicemail, deps: AnalysisDeps, force: bool = False) -> dict:
    """Synchronous wrapper (for the sync routes): runs `analyze` on its own event loop."""
    import asyncio

    return asyncio.run(analyze(vm, deps, force))


def bundle_parts(bundle: dict) -> dict[str, tuple[type, dict]]:
    """The bundle's typed models: `{task: (output_model, data)}` — for scoring and the API."""
    return {
        "summary": (SummaryOut, bundle["summary"]["data"]),
        "extraction": (ExtractionOut, bundle["extraction"]["data"]),
        "intent_urgency": (IntentOut, bundle["intent_urgency"]["data"]),
        "routing": (RoutingOut, bundle["routing"]["data"]),
        "sentiment": (SentimentOut, bundle["sentiment"]["data"]),
        "translation": (TranslationOut, bundle["translation"]["data"]),
        "draft_reply": (DraftOut, bundle["draft_reply"]["data"]),
    }


def urgency_of(bundle: dict) -> int:
    """The urgency the queue is ordered by: the AI's, from the intent_urgency task."""
    parts = bundle_parts(bundle)
    intent = parts["intent_urgency"][0].model_validate(parts["intent_urgency"][1])
    return int(intent.urgency)


def team_of(bundle: dict) -> str:
    parts = bundle_parts(bundle)
    return parts["routing"][0].model_validate(parts["routing"][1]).team
