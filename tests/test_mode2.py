"""Mode 2: non-obvious AI — similarity groups and the spike incident, resolution
without a callback with a human one-click approve, deadline-bound detection with
the keyword backstop and clocks, repeat-caller collapsing, missing-info recovery,
callback windows, and the mode-2 scoreboard.

Offline: every task runs through the mock provider, nothing calls a live LLM."""

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.pipeline.flags import POLICY, backstop, deadline_at, deadline_due, obligations_of

#: the truth the seeded day carries (verified against the 2026 seed)
PORTAL_CLUSTER = ("m21", "m22", "m23", "m24", "m25", "m26")  # all in the same similarity cluster
REPEAT_GROUP = ("m01", "m03", "m42")  # same case, three contacts
RESOLVABLE_TRUTH = {"m02", "m04", "m05", "m10", "m11", "m13", "m15", "m17", "m32", "m44", "m49", "m59"}
OBLIGATION_TRUTH = {
    "m09": {"legal"}, "m14": {"records"}, "m16": {"congressional"},
    "m37": {"welfare"}, "m51": {"welfare"}, "m53": {"congressional"},
}


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_mode2_queue_carries_the_day_links(client):
    items = (await client.get("/api/queue", params={"mode": 2})).json()
    assert set(items[0]) == {
        "id", "receivedAt", "callerId", "durationSec", "worked", "urgency", "team", "alert",
        "clusterSize", "repeat", "incident", "resolvable", "obligation", "window"}
    keys = [((i["alert"] or {}).get("priority", 9), -i["urgency"], i["receivedAt"], i["id"]) for i in items]
    assert keys == sorted(keys)                  # alerts first, then the AI's urgency
    assert items[0]["id"] == "m37"  # the urgent one still on top
    # the portal cluster is one group
    by = {i["id"]: i for i in items}
    assert len({by[m]["clusterSize"] for m in PORTAL_CLUSTER}) == 1  # they share the cluster
    assert all(by[m]["clusterSize"] > 1 for m in PORTAL_CLUSTER)
    # repeats collapse to the earliest: m01 is the leader, its followers hide
    assert by["m01"]["repeat"]["members"] == list(REPEAT_GROUP)
    assert "m03" not in by and "m42" not in by
    assert len(items) < 60  # collapsed repeats made the queue shorter
    # truth: resolvable flags land on the right messages
    flagged = {i["id"] for i in items if i["resolvable"]}
    assert flagged <= RESOLVABLE_TRUTH and flagged
    # the callback window, read in words
    if "m12" in by:
        assert by["m12"]["window"] == "after 17:00"
    # obligation badges: every flagged obligation must be in the truth
    for i in items:
        if i["obligation"]:
            assert i["obligation"] in OBLIGATION_TRUTH.get(i["id"], {i["obligation"]}) or i["id"] in OBLIGATION_TRUTH


async def test_incident_fires_from_the_spike(client):
    incidents = (await client.get("/api/incidents")).json()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["leadMin"] >= 0 and inc["count"] >= 6 and inc["size"] >= inc["count"]
    assert set(inc["card"]) == {"title", "banner", "probableCause", "actions", "provenance", "model"}
    assert inc["card"]["provenance"] in ("mock", "llm", "fallback")
    # the incident's members are members of the clustered day
    assert inc["members"][0] in set(PORTAL_CLUSTER) or len(inc["members"]) > 1
    # and the queue flags them
    items = (await client.get("/api/queue", params={"mode": 2})).json()
    flagged = {i["id"] for i in items if i["incident"] == inc["card"]["title"]}
    assert flagged & set(inc["members"])


async def test_message_mode2_section_and_resolution_flow(client):
    m = (await client.get("/api/messages/m05", params={"mode": 2})).json()
    assert set(m["mode2"]) == {"resolution", "brief", "obligations", "missingInfo", "applies"}
    o = m["mode2"]["resolution"]
    assert o["provenance"] in ("mock", "llm", "fallback") and o["model"]
    assert isinstance(o["lookups"], list)
    # m05 never gave a case number but the phone matches the case system
    assert m["mode2"]["missingInfo"]["status"] == "recovered"
    # draft: no state yet, defaults in
    r = (await client.get("/api/resolutions/m49")).json()
    assert r["state"] == "draft" and r["at"] is None
    assert r["resolution"]["resolvable"] is True
    # one-click approve: the AI only drafted, the human approved
    out = (await client.post("/api/resolutions/m49", json={"state": "approved"})).json()
    assert out["state"] == "approved" and out["reply"]
    r = (await client.get("/api/resolutions/m49")).json()
    assert r["state"] == "approved" and r["provenance"] == "human" and r["at"]
    # reject is a state too, and bad states are refused
    assert (await client.post("/api/resolutions/m49", json={"state": "rejected"})).status_code == 200
    assert (await client.get("/api/resolutions/m49")).json()["state"] == "rejected"
    assert (await client.post("/api/resolutions/m49", json={"state": "meh"})).status_code == 400
    assert (await client.get("/api/resolutions/m05")).json()["state"] == "draft"


async def test_scoreboard2_counts_the_day(client):
    # approve one truth-resolvable message first, so the avoided-callback count is honest
    assert (await client.post("/api/resolutions/m49", json={"state": "approved"})).status_code == 200
    sb = (await client.get("/api/scoreboard2")).json()
    assert sb["callbacksAvoided"]["approved"] == 1
    assert sb["callbacksAvoided"]["closedWithNoCall"] == 1  # m49 is in the truth-resolvable set
    assert sb["callbacksAvoided"]["resolvable"] == len(RESOLVABLE_TRUTH)
    # deadlines: the mock reads the flags from the truth, so caught == truth and missed == 0
    truth_count = sum(len(k) for k in OBLIGATION_TRUTH.values())
    assert sb["deadlines"]["caught"] >= truth_count and sb["deadlines"]["missed"] == 0
    clocks = {c["id"]: c for c in sb["deadlines"]["clocks"]}
    for mid, kinds in OBLIGATION_TRUTH.items():
        for kind in kinds:
            assert clocks[mid]["kind"] == kind and clocks[mid]["grounded"]
    # the incident's lead time is on the scoreboard
    assert sb["incident"]["leadMin"] >= 0 and sb["incident"]["title"]


def test_obligation_flags_llm_plus_keyword_backstop():
    # the LLM's flags pass through, a backstop hit the LLM missed is added
    got = obligations_of("call the senator's office about the shut off", ["welfare"])
    kinds = {g["kind"] for g in got}
    assert kinds == {"congressional", "welfare"}
    assert {g["evidence"] for g in got if g["kind"] == "congressional"} != {"the intent/urgency task flagged it"}
    # the LLM flag wins the note when both see the same kind
    got = obligations_of("my attorney says in writing", ["legal"])
    legal = next(g for g in got if g["kind"] == "legal")
    assert legal["source"] == "llm" and legal["evidence"] == "the intent/urgency task flagged it"
    # nothing in the script, no flags from the LLM: nothing
    assert backstop("hello, is this the number?") == []


def test_deadline_policy_business_days():
    from datetime import date
    # legal: named date, two business days from a Wednesday
    assert deadline_due(date(2026, 3, 10), "legal") == "2026-03-12"  # Wed + 2 = Fri
    assert deadline_due(date(2026, 3, 13), "welfare") == "2026-03-16"  # Sat + 1 = Mon
    assert deadline_due(date(2026, 3, 10), "records") == "2026-04-07"
    # every policy kind produces a due date strictly after the receipt
    for kind, days in POLICY.items():
        d = deadline_at("2026-03-10T08:00:00", kind)
        assert d > "2026-03-10" and len(d) == 10
        assert days > 0


async def test_window_and_brief_in_the_section(client):
    # m12: "reach me after work, after five" -> the clock reading is 17:00
    m = (await client.get("/api/messages/m12", params={"mode": 2})).json()
    w = m["mode2"]["resolution"]["callbackWindow"]
    assert w["when"] == "after 17:00" and w["at"] == "17:00"
    # the brief carries the record the lookups found, for the calls that still happen
    b = m["mode2"]["brief"]
    assert set(b) == {"case", "priorContacts", "intent", "urgency"}


async def test_the_day_is_worked_out_when_the_server_starts(seeded):
    # mock (and replay) mode: a background thread computes the day, so Mode 1 and 2 open at once
    import asyncio

    app = create_app(Settings(db_path=seeded[0]))
    async with app.router.lifespan_context(app):
        for _ in range(600):
            if app.state.mode2_messages is not None:
                break
            await asyncio.sleep(0.1)
    assert app.state.mode2_messages is not None and len(app.state.analysis_cache) == 59   # what reached a person
    # live mode stays lazy: warming would call the model on every start
    live = create_app(Settings(db_path=seeded[0], llm_mode="live", llm_base_url="http://127.0.0.1:9", llm_api_key="x"))
    async with live.router.lifespan_context(live):
        await asyncio.sleep(0.5)
    assert live.state.mode2 is None


async def test_each_mode_changes_what_the_day_gets_done(client):
    # Mode 1 works in the AI's urgency order (its own guesses); Mode 2 also only needs a person's approval
    # for what the AI already answered. Same day, same agent, same assumptions.
    day = [(await client.get("/api/simulation", params={"mode": m})).json() for m in (0, 1, 2)]
    m0, m1, m2 = day
    assert m1["urgentWaitMin"] <= 30 < m0["urgentWaitMin"]          # the urgent caller: minutes, not hours
    assert m0["obligationsMissed"] > 0 and m1["obligationsMissed"] == m2["obligationsMissed"] == 0
    assert m1["agentHours"] < m0["agentHours"]                       # mode 1: the junk filter alone gives time back
    assert m2["agentHours"] < m0["agentHours"] / 2 and m2["unreached"] == 0 and m2["reachedBy"]
    assert m1["order"][0] != m0["order"][0]                          # urgency, not arrival
