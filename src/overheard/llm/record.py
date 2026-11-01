"""`overheard record`: drive one seeded day through the *real* pipeline with
`write=True`, so every provider answer lands in the response store as a fixture.

By default the provider is the mock (the stored fixtures are its answers); under
`OVERHEARD_LLM_MODE=record` the live host is used and everything that reaches it
is saved, so the same day replays offline later. The day is computed on a fresh
database, so nothing is short-circuited by an existing analysis table and the
store is the only thing record leaves behind.
"""

import json
import sqlite3

from overheard.adapters.backend.mock import MockCaseBackend
from overheard.config import Settings
from overheard.data.generator import seed
from overheard.llm import ResponseStore, build_provider
from overheard.llm import tasks as _tasks
from overheard.pipeline.analyze import AnalysisDeps, analyze_sync
from overheard.pipeline.mode2 import Mode2Deps, day_bundles


def _voicemails(con: sqlite3.Connection) -> list:
    from overheard.data.models import Voicemail

    rows = con.execute("SELECT * FROM voicemails ORDER BY received_at, id").fetchall()
    return [Voicemail(id=r["id"], receivedAt=r["received_at"], callerId=r["caller_id"],
                      durationSec=r["duration_sec"], lang=r["lang"], script=r["script"],
                      truth=json.loads(r["truth"])) for r in rows]


def record_day(db_path, settings: Settings, store_path=None) -> dict:
    """Seed `db_path` fresh, run every task on the day with `write=True`, and
    return a summary: per-task counts (and provenances) of what was computed.

    The per-message bundle and the mode-2 day bundles (clusters, repeats,
    missing-info, incidents) both go through the shared runner, so `incident`
    and `resolution` land in the store alongside the seven per-message tasks.
    """
    counts = seed(db_path, settings.seed)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS analysis (voicemail TEXT NOT NULL, task TEXT NOT NULL, model TEXT, "
        "data TEXT NOT NULL, provenance TEXT NOT NULL, PRIMARY KEY (voicemail, task))"
    )
    store = ResponseStore(store_path or settings.llm_responses_path)
    provider = build_provider(settings, store)
    # `run_task` stores under the model name it's told; the mock runs under
    # "mock", a live host under its configured model.
    model = settings.llm_model or "mock"

    vms = _voicemails(con)
    analysis = AnalysisDeps(con=con, store=store, provider=provider, model=model, write=True)
    backend = MockCaseBackend(con)
    bundles = {v.id: analyze_sync(v, analysis) for v in vms}
    day = day_bundles(vms, bundles, backend,
                      Mode2Deps(con, store, provider, model, write=True))
    con.close()

    per_message = sum(1 for b in bundles.values() for t in b if t in _tasks.TASKS)
    mode2_llm = len(day["incidents"]) + len(vms)  # incident cards + one resolution per message
    return {
        "db": str(db_path),
        "seed": settings.seed,
        "llm_mode": settings.llm_mode,
        "model": model,
        "voicemails": len(vms),
        "seeded": counts,
        "llm_calls": per_message + mode2_llm,
        "store": str(store.path),
        "fixtures": len(list(store.path.glob("*.json"))),
        "bundles": bundles,  # per-message bundles the run produced (for replay comparison)
        "day": day,  # mode-2 bundles: clusters, repeats, missingInfo, incidents
    }
