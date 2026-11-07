"""Mode 1: the AI analysis bundle, the urgency queue, corrections and accuracy.

Offline: every task runs through the mock provider, nothing calls a live LLM."""

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings

TASKS = ("summary", "intent_urgency", "routing", "extraction", "sentiment", "translation", "draft_reply")
FIELDS = ("caller", "callbackNumber", "caseId", "program", "requestedAction")


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.delete("/api/corrections")
        yield c


async def test_mode1_queue_is_sorted_by_urgency_with_teams(client):
    items = (await client.get("/api/queue", params={"mode": 1})).json()
    assert len(items) == 60
    assert set(items[0]) == {"id", "receivedAt", "callerId", "durationSec", "worked", "urgency", "team", "alert"}
    # code-word alerts first (safety before the rest), then the AI's urgency
    keys = [((i["alert"] or {}).get("priority", 9), -i["urgency"], i["receivedAt"], i["id"]) for i in items]
    assert keys == sorted(keys)
    assert {i["id"] for i in items if i["alert"]} == {"m09", "m16", "m37", "m53"}
    top = items[0]  # m37: Eleanor Voss, urgent hardship
    assert top["id"] == "m37" and top["urgency"] == 5 and top["team"] == "escalations"


async def test_mode0_queue_stays_the_plain_inbox(client):
    items = (await client.get("/api/queue", params={"mode": 0})).json()
    assert "urgency" not in items[0] and items[0]["id"] == "m01"


async def test_mode1_message_has_the_full_analysis_bundle(client):
    m = (await client.get("/api/messages/m37", params={"mode": 1})).json()
    a = m["analysis"]
    assert a["id"] == "m37" and a["words"] == m["words"]
    assert set(a) >= set(TASKS)
    for t in TASKS:
        entry = a[t]
        assert set(entry) == {"data", "provenance", "model"}, t
        assert entry["provenance"] in ("mock", "llm", "fallback")
        assert entry["model"]
    # every field the front end badges has a confidence
    for f in FIELDS:
        assert 0.0 <= a["extraction"]["data"][f]["confidence"] <= 1.0


async def test_extraction_spans_point_into_the_script(client):
    m = (await client.get("/api/messages/m37", params={"mode": 1})).json()
    script = m["script"]
    for f in FIELDS:
        d = m["analysis"]["extraction"]["data"][f]
        span, value = d["span"], d["value"]
        if span is None:
            continue
        s, e = span
        assert 0 <= s < e <= len(script), (f, span)
        span_text = script[s:e].lower()
        if f == "callbackNumber":
            # the span covers the SPOKEN number: every digit must be spoken in it
            spoken = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
                      "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
            heard = {w for w in span_text.split() if w in spoken}
            assert {d for d in (value or "") if d.isdigit()} <= {spoken[w] for w in heard}, (f, span_text)
        else:
            # the span's words back the value: one of the value's words was heard in it
            assert {w.strip(" ,.!?'").lower() for w in (value or "").split()} & \
                   {w.strip(" ,.!?'").lower() for w in span_text.split()}, (f, span_text, value)


async def test_corrections_round_trip(client):
    r = await client.post("/api/corrections", json={"voicemail": "m37", "task": "extraction",
                                                    "field": "caseId", "value": "FBS-366098"})
    assert r.status_code == 200
    r = await client.post("/api/corrections", json={"voicemail": "m37", "task": "extraction",
                                                    "field": "callbackNumber", "value": None})
    assert r.status_code == 200
    rows = (await client.get("/api/corrections", params={"voicemail": "m37"})).json()
    assert [(r["task"], r["field"], r["value"]) for r in rows] == [
        ("extraction", "caseId", '"FBS-366098"'),
        ("extraction", "callbackNumber", None),
    ]
    assert all(r["provenance"] == "human" for r in rows)
    assert (await client.get("/api/corrections", params={"voicemail": "m01"})).json() == []
    bad = await client.post("/api/corrections", json={"voicemail": "m99", "task": "x", "field": "y", "value": "nope"})
    assert bad.status_code == 404
    assert (await client.delete("/api/corrections")).json() == {"cleared": True}
    assert (await client.get("/api/corrections")).json() == []


async def test_accuracy_scores_all_tasks_and_counts_corrections(client):
    acc = (await client.get("/api/accuracy")).json()
    assert acc["messages"] == 60 and acc["corrections"] == 0
    for k in ("intent_urgency", "routing", "extraction"):
        assert isinstance(acc[k], float) and 0.0 <= acc[k] <= 1.0, k
    base = {k: acc[k] for k in ("intent_urgency", "routing", "extraction")}
    # a human fix to an extracted fact can only keep or raise extraction accuracy
    assert (await client.post("/api/corrections", json={
        "voicemail": "m37", "task": "extraction", "field": "caller", "value": "Eleanor Voss"})).status_code == 200
    assert (await client.post("/api/corrections", json={
        "voicemail": "m37", "task": "extraction", "field": "callbackNumber", "value": "+1-865-555-0190"})).status_code == 200
    acc2 = (await client.get("/api/accuracy")).json()
    assert acc2["corrections"] == 2
    assert acc2["extraction"] >= base["extraction"]
    assert acc2["intent_urgency"] == base["intent_urgency"] and acc2["routing"] == base["routing"]
    assert (await client.delete("/api/corrections")).status_code == 200
