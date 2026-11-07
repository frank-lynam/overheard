"""Retroactive relevance: the planted overlooked "error 4012" contacts (in the four weeks before today's outage,
taken for password resets and never ticketed) are recovered from the spike's suggested definition."""

import json
import sqlite3

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data.generator import seed
from overheard.pipeline.retro import candidates


@pytest.fixture(scope="module")
def day_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("retro") / "day.db"     # its own: the app writes to it
    seed(path, 2026)
    return path


@pytest.fixture
async def client(day_db):
    path = day_db
    app = create_app(Settings(db_path=path))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        yield c, path


async def test_the_planted_overlooked_contacts_are_recovered(client):
    c, path = client
    con = sqlite3.connect(path)
    planted = set(json.loads(con.execute("SELECT value FROM meta WHERE key = 'overlooked'").fetchone()[0]))
    assert len(planted) == 40
    s = (await c.get("/api/retro")).json()["suggested"]
    assert s["origin"] == "today's spike" and s["team"] == "portal-it" and "4012" in s["description"]
    assert s["since"] == "2026-02-10" and s["until"] == "2026-03-10"
    cands = {x["id"] for x in candidates(con, s)}
    assert planted <= cands and len(cands - planted) <= 4           # retrieval: all of them, little else
    r = (await c.post("/api/retro")).json()
    got = {i["id"] for i in r["items"]}
    assert len(got & planted) >= 34 and not got - planted           # confirmed: nearly all, nothing else
    m = r["summary"]
    assert m["count"] == len(got) and m["leadDays"] >= 25 and 1 < m["agentHours"] < 5
    assert all(i["overlooked"] == "never ticketed" and i["recordedAs"] == "password-reset" and i["matched"]
               for i in r["items"])
    assert "$" not in json.dumps(r)                                  # hours, not dollars


async def test_a_definition_outside_the_window_finds_nothing(client):
    c, _ = client
    r = (await c.post("/api/retro", json={"description": "Sign-in fails with error 4012", "examples": [],
                                          "since": "2025-01-01", "until": "2025-03-01", "team": "portal-it"})).json()
    assert r["summary"]["count"] == 0
