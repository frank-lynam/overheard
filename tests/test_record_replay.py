"""Record, then replay: the same day run through the *real* pipeline again in
replay mode must come out byte-identical, answered entirely from the response
store — no network, no fallbacks.

`record_day` computes the day on a fresh database with `write=True`, so its
bundles are what the record left behind. The replay builds the same deps from
the same store with `llm_mode="replay"` against a *fresh* database (empty
analysis table, so nothing is short-circuited before the store): every task
must be a store hit. A miss would fall back to the from-truth mock and surface
as `fallback` provenance, so the provenance assertion is the zero-miss proof,
and the socket guard is the zero-network proof."""

import json
import socket
import sqlite3

from overheard.adapters.backend.mock import MockCaseBackend
from overheard.config import Settings
from overheard.data.generator import seed
from overheard.data.models import Voicemail
from overheard.llm import ResponseStore, build_provider
from overheard.llm.record import record_day
from overheard.llm.replay import ReplayProvider
from overheard.pipeline.analyze import AnalysisDeps, analyze_sync
from overheard.pipeline.mode2 import Mode2Deps, day_bundles, message_mode2


def _voicemails(con) -> list[Voicemail]:
    rows = con.execute("SELECT * FROM voicemails ORDER BY received_at, id").fetchall()
    return [Voicemail(id=r["id"], receivedAt=r["received_at"], callerId=r["caller_id"],
                      durationSec=r["duration_sec"], lang=r["lang"], script=r["script"],
                      truth=json.loads(r["truth"])) for r in rows]


def _fresh_db(db, settings):
    """A freshly seeded database with the analysis table the pipeline wants."""
    seed(db, settings.seed)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS analysis (voicemail TEXT NOT NULL, task TEXT NOT NULL, model TEXT, "
        "data TEXT NOT NULL, provenance TEXT NOT NULL, PRIMARY KEY (voicemail, task))"
    )
    return con


def test_record_then_replay_is_identical_and_offline(tmp_path, monkeypatch):
    db = tmp_path / "rec.db"
    store_path = tmp_path / "fixtures"
    settings = Settings(llm_mode="mock", llm_model="mock", db_path=db, llm_responses_path=store_path)
    rec = record_day(db, settings)

    assert rec["voicemails"] > 0
    fixtures = len(list(store_path.glob("*.json")))
    assert fixtures > 0
    assert rec["llm_calls"] > fixtures  # repeats and incidents share fixtures (dedup)

    # zero network: any non-UNIX socket from here on fails the test (the event
    # loop's self-pipe is AF_UNIX, which is fine — it's a local pipe, not the net)
    def _no_net(family=socket.AF_INET, *_a, **_k):
        if family != socket.AF_UNIX:
            raise AssertionError("network socket opened during replay")
        return _real_socket(family, *_a, **_k)

    _real_socket = socket.socket
    monkeypatch.setattr(socket, "socket", _no_net)

    # replay: the *same* real pipeline, but the provider is the store only
    store = ResponseStore(store_path)
    provider = build_provider(Settings(llm_mode="replay", llm_model="mock", db_path=db,
                                       llm_responses_path=store_path), store)
    assert isinstance(provider, ReplayProvider)

    # fresh database, same seed: the analysis table is empty, so every task
    # must be answered from the store, not the database
    con = _fresh_db(tmp_path / "replay.db", settings)
    vms = _voicemails(con)
    deps = AnalysisDeps(con=con, store=store, provider=provider, model="mock")
    replay_bundles = {v.id: analyze_sync(v, deps) for v in vms}

    # byte-identical to what the record produced, and every task from the store
    for vm in vms:
        rec_b, rep_b = rec["bundles"][vm.id], replay_bundles[vm.id]
        assert rep_b == rec_b, f"{vm.id}: replay bundle differs from the recorded one"
        for task, out in rec_b.items():
            if task in ("id", "words"):
                continue
            assert out["provenance"] == "llm", f"{vm.id}/{task}: replay fell off the store"

    # the mode-2 bundles (clusters, repeats, missing info, incidents) match too
    backend = MockCaseBackend(con)
    m2 = Mode2Deps(con, store, provider, "mock")
    day = day_bundles(vms, replay_bundles, backend, m2)
    assert day["clusters"] == rec["day"]["clusters"]
    assert day["repeats"] == rec["day"]["repeats"]
    assert day["missingInfo"] == rec["day"]["missingInfo"]
    assert day["incidents"] == rec["day"]["incidents"]
    for inc in day["incidents"]:
        assert inc["card"]["provenance"] == "llm"

    # per-message mode-2 (resolution, brief, obligations, missing info) too
    for vm in vms:
        assert message_mode2(vm, replay_bundles[vm.id], backend, m2) == message_mode2(
            vm, rec["bundles"][vm.id], backend, m2)

    con.close()

    # the console's demo walk (junk filter, applies, tickets with the move, the retro search) replays the same,
    # against another fresh database, with every new task in the store
    assert {"junk_classify", "applies_triage", "problem_classify", "team_propose", "retro_match"} <= set(rec["per_task"])
    from fastapi.testclient import TestClient

    from overheard.app import create_app
    from overheard.llm.record import demo_sequence
    walk_db = tmp_path / "walk.db"
    seed(walk_db, settings.seed)
    app = create_app(Settings(llm_mode="replay", llm_model="mock", db_path=walk_db, llm_responses_path=store_path))
    client = TestClient(app)
    misses = []
    real_complete = app.state.provider.complete

    async def counting(task, model):
        out = await real_complete(task, model)
        if out is None:
            misses.append(task.name)
        return out
    app.state.provider.complete = counting
    walk = demo_sequence(lambda m, p, b=None: client.request(m, p, json=b).json())
    assert not misses, misses
    assert walk == rec["demo"] and walk["learned"] == "benefits-processing"

    # the store was read, not written to, by the replay
    assert len(list(store_path.glob("*.json"))) == fixtures
