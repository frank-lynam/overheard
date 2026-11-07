"""`overheard record`: drive one seeded day through the *real* pipeline with
`write=True`, so every provider answer lands in the response store as a fixture.

By default the provider is the mock (the stored fixtures are its answers); under
`OVERHEARD_LLM_MODE=record` the live host is used and everything that reaches it
is saved, so the same day replays offline later. The day is computed on a fresh
database, so nothing is short-circuited by an existing analysis table and the
store is the only thing record leaves behind.

Then the console's own routes are driven through `demo_sequence`, the steps the
demo script (docs/DESIGN.md) takes: the junk filter, the Mode 2 queue and every
message's section (with the applies triage), the tickets with the demo's move,
and the retro search. Team proposals depend on what people decided before them,
so a replay is only all hits when it follows the same sequence: the offline
rehearsal (tools/rehearse_offline.py) runs this same function against the
replay server.
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


def _per_task(store: ResponseStore) -> dict[str, int]:
    """Fixture files per task (files are named task-key-model.json)."""
    out: dict[str, int] = {}
    for f in store.path.glob("*.json"):
        name = f.name.split("-")[0]
        out[name] = out.get(name, 0) + 1
    return dict(sorted(out.items()))


def _voicemails(con: sqlite3.Connection) -> list:
    from overheard.data.models import Voicemail

    rows = con.execute("SELECT * FROM voicemails ORDER BY received_at, id").fetchall()
    return [Voicemail(id=r["id"], receivedAt=r["received_at"], callerId=r["caller_id"],
                      durationSec=r["duration_sec"], lang=r["lang"], script=r["script"],
                      truth=json.loads(r["truth"])) for r in rows]


# The demo's ticket decisions, in order: the first 22-B letter ticket (proposed to Outreach) is moved to Benefits
# Processing; the next one is then proposed there, and accepted.
MOVE_TO = "benefits-processing"


def demo_sequence(call) -> dict:
    """The demo's walk through the console, as API calls. `call(method, path, body=None)` returns the JSON; it's a
    test client when recording, HTTP against the replay server when rehearsing. Returns what it saw."""
    out: dict = {"junk": call("GET", "/api/junk")["counts"]}
    q2 = call("GET", "/api/queue?mode=2")
    out["queued"] = len(q2)
    applies = 0
    for item in call("GET", "/api/queue?mode=1"):                  # every message's Mode 2 section, applies too
        sec = call("GET", f"/api/resolutions/{item['id']}")
        applies += sum(a["verdict"] == "applies" for a in sec["applies"]["verdicts"])
    out["applies"] = applies
    first = call("POST", "/api/tickets/reveal", {})["made"][0]
    call("POST", f"/api/tickets/{first['ticket_id']}/decide", {"action": "move", "team": MOVE_TO})
    nxt: list = []
    while not any(t["problem_type"] == first["problem_type"] for t in nxt):
        nxt = call("POST", "/api/tickets/reveal", {})["made"]
        if not nxt:
            break
    learned = next((t for t in nxt if t["problem_type"] == first["problem_type"]), None)
    if learned:
        call("POST", f"/api/tickets/{learned['ticket_id']}/decide", {"action": "accept"})
    call("POST", "/api/tickets/reveal", {"all": True})
    tickets = call("GET", "/api/tickets")
    out["tickets"] = tickets["counts"]
    out["learned"] = learned and learned["proposed_team"]
    retro = call("POST", "/api/retro")
    out["retro"] = retro["summary"]
    return out


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

    # the console's routes, in the demo's order, with every answer kept
    from fastapi.testclient import TestClient

    from overheard.app import create_app
    app = create_app(settings.model_copy(update={"db_path": db_path}))
    app.state.provider, app.state.store, app.state.write = provider, store, True
    client = TestClient(app)    # no lifespan: nothing warms up behind the walk's back

    def call(method, path, body=None):
        r = client.request(method, path, json=body)
        r.raise_for_status()
        return r.json()
    walk = demo_sequence(call)

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
        "per_task": _per_task(store),
        "demo": walk,
        "bundles": bundles,  # per-message bundles the run produced (for replay comparison)
        "day": day,  # mode-2 bundles: clusters, repeats, missingInfo, incidents
    }
