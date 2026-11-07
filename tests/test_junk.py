"""The junk filter: robocalls, scams, silence and pocket dials kept out of the human queue (from Mode 1 on), never a
real caller; unsure and safety calls always reach a person; anything filtered can be reopened."""

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data.models import Voicemail
from overheard.pipeline.junk import JunkRules, decide, rule_for


def vm(script, caller="+15550000000", id_="x1"):
    return Voicemail(id=id_, receivedAt="2026-03-10T09:00", callerId=caller, durationSec=40, lang="en", script=script,
                     truth={"intent": "other", "urgency": 1, "rootCause": "junk", "team": "general",
                            "callbackNumber": caller})


RULES = JunkRules.load()
never = lambda v: pytest.fail("the LLM shouldn't be asked")   # noqa: E731


def test_each_rule():
    assert rule_for(vm("(silence)"), RULES, {})[0] == "too-short"
    assert rule_for(vm("(a click) hello?"), RULES, {})[0] == "too-short"
    assert rule_for(vm("Hi there it's about your account", "+1-202-555-0199"), RULES, {})[0] == "blocked-number"
    same = vm("Call us back today about your solar savings")
    assert rule_for(same, RULES, {"call us back today about your solar savings": 3})[0] == "same-script"
    assert rule_for(vm("Your extended warranty is about to expire, so call us"), RULES, {})[0] == "scripted"
    assert rule_for(vm("Sign in broken. E-4012. Thanks."), RULES, {}) is None      # short, but a real caller


def test_unsure_and_safety_reach_a_person():
    unsure = decide(vm("Hello, is this the right office, I think"), False, RULES, {},
                    lambda v: ("unsure", "Can't tell.", "llm"))
    assert unsure["disposition"] == "queued" and unsure["verdict"] == "unsure"
    # a robocall-looking call with a safety code word: never filtered, not even by a rule
    safety = decide(vm("Press one now. I'm going to hurt myself."), True, RULES, {}, never)
    assert safety["disposition"] == "queued" and safety["decidedBy"] == "safety"
    junk = decide(vm("We can lower your bills, call us"), False, RULES, {}, lambda v: ("junk", "A pitch.", "llm"))
    assert junk["disposition"] == "filtered" and junk["decidedBy"] == "llm"


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        yield c


async def test_every_junk_call_is_filtered_and_no_real_one(client):
    got = (await client.get("/api/junk")).json()
    c = got["counts"]
    assert (c["calls"], c["junk"], c["caught"], c["realFiltered"], c["falseJunkRate"]) == (180, 121, 121, 0, 0.0)
    assert all(f["id"].startswith("j") or f["id"] == "m06" for f in got["filtered"])   # m06: the silent hang-up
    assert {f["decidedBy"].split(":")[0] for f in got["filtered"]} <= {"rule", "llm"}
    queued = {i["id"] for i in (await client.get("/api/queue", params={"mode": 1})).json()}
    assert not queued & {f["id"] for f in got["filtered"]}
    assert {"m24", "m28", "m47"} <= queued                     # real calls that look like junk reach a person


async def test_a_reopened_call_reaches_the_queue(client, seeded):
    first = (await client.get("/api/junk")).json()["filtered"][0]["id"]
    assert (await client.post(f"/api/junk/{first}/reopen")).status_code == 200
    assert first in {i["id"] for i in (await client.get("/api/queue", params={"mode": 1})).json()}
    assert first not in {f["id"] for f in (await client.get("/api/junk")).json()["filtered"]}
    assert (await client.post(f"/api/junk/{first}/reopen")).status_code == 404   # not filtered any more
    seeded[1].execute("DELETE FROM junk_reopened")                              # the database is shared: tidy up
    seeded[1].commit()
