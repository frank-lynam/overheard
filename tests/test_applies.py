"""Stage [D], applies triage: seeded messages map to the rules that cover them, a rule out of its window is never
offered, every "applies" quotes the caller, and the verdicts reach the Mode 2 view and the ticket."""

import asyncio
import json
import sqlite3
from importlib import resources

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data.generator import seed
from overheard.data.models import Voicemail
from overheard.llm.mock import MockProvider
from overheard.llm.run import run_task
from overheard.pipeline.applies import candidates, catalogue, check, in_force, triage, truly_applies


def today() -> list[Voicemail]:
    d = json.loads(resources.files("overheard.data").joinpath("seed_today.json").read_text())
    return [Voicemail(**m) for m in d["voicemails"] if not m["truth"]["junk"]]


def run(task):
    return run_task(MockProvider(), task, "mock")


def test_seeded_messages_map_to_the_expected_rules():
    want = got = applied = wrong = 0
    for v in today():
        day = v.receivedAt[:10]
        expected = {r["id"] for r in catalogue() if in_force(r, day) and truly_applies(v, r)}
        offered = {r["id"] for r in candidates(v, day)}
        want += len(expected)
        got += len(expected & offered)
        verdicts = asyncio.run(triage(v, day, run))["verdicts"]
        for a in verdicts:
            if a["verdict"] == "applies":
                applied += 1
                wrong += a["ruleId"] not in expected
    assert want > 35 and got / want >= 0.9          # retrieval finds the rule for nearly every message it covers
    assert applied >= 0.75 * want and wrong == 0    # the mock (from the truth) agrees, now and then unsure, never wrong
    by = {v.id: v for v in today()}
    ids = lambda mid: {a["ruleId"] for a in asyncio.run(triage(by[mid], "2026-03-10", run))["verdicts"]  # noqa: E731
                       if a["verdict"] != "does_not_apply"}        # applies, or put to a person as unsure
    assert "form-22b-reverification" in ids("m10")        # "those twenty-two B letters, the re-verification"
    assert "portal-outage-4012" in ids("m27")             # "E dash forty twelve"
    assert "congressional-five-days" in ids("m53")        # the senator's caseworker


def test_an_expired_rule_is_never_offered():
    expired = next(r for r in catalogue() if r["id"] == "cola-letters-2025")
    assert not in_force(expired, "2026-03-10")
    for v in today():
        assert expired["id"] not in {r["id"] for r in candidates(v, v.receivedAt[:10])}
    m20 = next(v for v in today() if v.id == "m20")               # a cost-of-living letter, but this year's
    assert m20.truth.rootCause in expired["causes"]
    assert expired["id"] not in {a["ruleId"] for a in asyncio.run(triage(m20, "2026-03-10", run))["verdicts"]}
    # and a verdict for a rule that wasn't offered (an LLM making one up) is dropped
    v = today()[0]
    offered = candidates(v, "2026-03-10")
    made_up = [{"rule_id": "cola-letters-2025", "verdict": "applies", "reason": "x", "quote": v.script[:10]}]
    assert check(v, offered, made_up) == []


def test_every_applies_quotes_the_caller():
    n = 0
    for v in today():
        for a in asyncio.run(triage(v, v.receivedAt[:10], run))["verdicts"]:
            if a["verdict"] == "applies":
                n += 1
                s, e = a["span"]
                assert a["quote"] and v.script[s:e] == a["quote"]
    assert n > 30
    # an "applies" whose words aren't in the message can't stand: it goes to a person as unsure
    v = today()[0]
    offered = candidates(v, "2026-03-10")
    out = check(v, offered, [{"rule_id": offered[0]["id"], "verdict": "applies", "reason": "Sure.",
                              "quote": "words nobody said"}])
    assert out[0]["verdict"] == "unsure" and out[0]["span"] is None


@pytest.fixture
async def client(tmp_path):
    seed(tmp_path / "day.db", 2026)
    app = create_app(Settings(db_path=tmp_path / "day.db"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        yield c, tmp_path / "day.db"


async def test_verdicts_reach_the_message_view_and_the_ticket(client):
    c, path = client
    m = (await c.get("/api/messages/m10", params={"mode": 2})).json()
    ap = m["mode2"]["applies"]
    assert ap["provenance"] in ("mock", "llm", "fallback")
    assert any(a["ruleId"] == "form-22b-reverification" and a["verdict"] != "does_not_apply" for a in ap["verdicts"])
    made = (await c.post("/api/tickets/reveal", json={"all": True})).json()["made"]
    t = next(t for t in made if "m53" in t["item_ids"])
    desc = sqlite3.connect(path).execute("SELECT description FROM mock_board WHERE board_id = ?",
                                         (t["board_id"],)).fetchone()[0]
    assert "Applies:" in desc and "Congressional inquiries" in desc and "heard:" in desc
