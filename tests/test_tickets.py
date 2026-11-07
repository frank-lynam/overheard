"""Memory and tickets: retrieval that captures similarity, proposals from the evidence, one ticket per problem,
decisions read back into the memory, and a move that changes the next proposal."""

import sqlite3

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data import db
from overheard.data.generator import seed
from overheard.memory.embed import MockEmbeddingProvider, cosine
from overheard.memory.store import Memory, doc


def test_memory_rebuilds_identically_from_the_seed(tmp_path):
    seed(tmp_path / "a.db", 2026)
    seed(tmp_path / "b.db", 2026)
    rows = lambda p: sqlite3.connect(p).execute(   # noqa: E731
        "SELECT * FROM memory_items ORDER BY item_id").fetchall() + sqlite3.connect(p).execute(
        "SELECT * FROM memory_events ORDER BY event_id").fetchall()
    assert rows(tmp_path / "a.db") == rows(tmp_path / "b.db")
    assert len(rows(tmp_path / "a.db")) > 2000


def test_similar_wording_scores_above_different_issues():
    e = MockEmbeddingProvider(["my payment did not arrive", "the portal sign in is broken",
                               "I got a letter about form 22-B"])
    a, b = e.embed("My March payment never arrived"), e.embed("The payment I was owed did not arrive this month")
    c = e.embed("I can't sign in to the portal, it shows an error")
    assert cosine(a, b) > cosine(a, c)


def small_memory(tmp_path, past):
    con = db.create(tmp_path / "m.db")
    m = Memory(con, "2026-03-10")
    for i, (ptype, text, team, when) in enumerate(past):
        m.record(f"p{i}:routing", f"c{i}", "routing", {"team": team}, when, text=text, team=team, problem_type=ptype)
    return m


def test_proposals_follow_the_evidence(tmp_path):
    bp = "benefits-processing"
    m = small_memory(tmp_path, [("returned-deposit", "My deposit came back to you", bp, "2025-06-01"),
                                ("returned-deposit", "The payment bounced, bank closed", bp, "2025-09-01"),
                                ("records-request", "I need a copy of my file", "records", "2025-07-01")])
    w = m.weigh(doc("returned-deposit", "My payment came back, the bank account was closed"))
    assert next(iter(w["shares"])) == "benefits-processing" and w["shares"]["benefits-processing"] >= 0.5
    assert all(e["ref"] in m.items for e in w["evidence"])                   # every evidence id is in the memory
    assert m.weigh(doc("garnishment-question", "Why is part of my payment being taken"))["shares"] == {}  # unknown
    # recording the same decision twice doesn't duplicate it
    assert not m.record("p0:routing", "c0", "routing", {"team": "x"}, "2025-06-01", text="t", team="x")


@pytest.fixture
async def client(tmp_path):
    seed(tmp_path / "day.db", 2026)
    app = create_app(Settings(db_path=tmp_path / "day.db"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        yield c


async def test_one_ticket_per_problem_and_decisions_read_back(client):
    made = (await client.post("/api/tickets/reveal", json={"all": True})).json()["made"]
    by = {t["item_id"]: t for t in made}
    assert "m14" in by and by["m14"]["proposed_team"] == "records"           # a records request: one ticket
    assert sum("m14" in t["item_ids"] for t in made) == 1
    assert "m02" not in {i for t in made for i in t["item_ids"]}              # a status question: no ticket
    outage = next(t for t in made if len(t["item_ids"]) == 28)               # the outage's 28 callers: one ticket
    assert outage["proposed_team"] == "portal-it" and outage["priority"] == 2
    assert by["m09"]["priority"] == 1                                        # code words: priority 1
    assert by["m16"]["proposed_team"] == "unknown" and by["m16"]["filed_in"] == "general"
    # nothing changes until a decision is read back
    t = by["m14"]
    assert (await client.get(f"/api/tickets/{t['ticket_id']}")).json()["status"] == "proposed"
    done = (await client.post(f"/api/tickets/{t['ticket_id']}/decide", json={"action": "accept"})).json()
    assert done["status"] == "accepted" and done["final_team"] == "records"
    got = (await client.get("/api/tickets")).json()
    assert got["counts"]["accepted"] == 1 and got["accuracy"]["accuracy"] > 0.8


async def test_a_move_changes_the_next_similar_proposal(client):
    first = (await client.post("/api/tickets/reveal", json={})).json()["made"][0]
    assert first["item_id"] == "m01" and first["proposed_team"] == "outreach"     # the 22-B letter: outreach
    moved = (await client.post(f"/api/tickets/{first['ticket_id']}/decide",
                               json={"action": "move", "team": "benefits-processing"})).json()
    assert moved["status"] == "moved" and moved["final_team"] == "benefits-processing"
    nxt = []
    while not any(t["problem_type"] == "form-22b-confusion" for t in nxt):
        nxt = (await client.post("/api/tickets/reveal", json={})).json()["made"]
        assert nxt, "ran out of tickets"
    assert nxt[0]["proposed_team"] == "benefits-processing"                    # learned from the move
    assert any(e["ref"] == "m01" for e in nxt[0]["evidence"])


async def test_an_outage_caller_outside_the_cluster_joins_the_incident_ticket(tmp_path):
    """Clustering by wording can miss callers who describe the outage in other words (a live model's summaries
    vary): the problem check puts them on the open incident's ticket, not tickets of their own."""
    from types import SimpleNamespace

    from overheard.api.routes import mode2_day
    seed(tmp_path / "day.db", 2026)
    app = create_app(Settings(db_path=tmp_path / "day.db"))
    import asyncio
    day = await asyncio.to_thread(mode2_day, SimpleNamespace(app=app))   # sync code, as in the app's routes
    inc = day["incidents"][0]
    left_out = ["m22", "m23", "m36"]
    inc["members"] = [m for m in inc["members"] if m not in left_out]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        made = (await c.post("/api/tickets/reveal", json={"all": True})).json()["made"]
        assert not any(t["item_id"] in left_out for t in made)
        got = (await c.get("/api/tickets")).json()["tickets"]
    outage = next(t for t in got if t["problem_type"] == "portal-sign-in-failure")
    assert set(left_out) <= set(outage["item_ids"]) and len(outage["item_ids"]) == 28
    assert "(28 callers)" in outage["summary"]
    assert sum(t["problem_type"] == "portal-sign-in-failure" for t in got) == 1


def test_a_decision_today_counts_however_it_was_worded(tmp_path):
    """Many near-identical old routings can fill the nearest neighbours; a person's move today on the same kind of
    problem is evidence anyway, and outweighs them."""
    old = [("form-22b-confusion", "The 22-B letter says my benefits will stop, what do I do?", "outreach",
            f"2023-0{i % 9 + 1}-01") for i in range(12)]                # templated, and years old
    m = small_memory(tmp_path, old)
    m.record("t:move", "m10", "move", {"from": "outreach", "to": "benefits-processing"}, "2026-03-10T11:55:00",
             text="Caller received a second Form 22B re-verification letter and already returned one",
             team="benefits-processing", problem_type="form-22b-confusion")
    w = m.weigh(doc("form-22b-confusion", "Caller sent Form 22-B in February and is afraid benefits will stop"))
    assert any(e["ref"] == "m10" for e in w["evidence"])
    assert next(iter(w["shares"])) == "benefits-processing"
    other = m.weigh(doc("records-request", "Caller sent Form 22-B in February and is afraid benefits will stop"))
    assert not any(e["ref"] == "m10" for e in other["evidence"])          # not for another kind of problem
