"""Mode 0: the inbox API, lookups, manual entries, and the 'work the queue' simulation."""

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.delete("/api/entries")
        yield c


async def test_the_inbox_shows_no_content(client):
    q = (await client.get("/api/queue")).json()
    assert len(q) == 60 and q[0]["id"] == "m01"
    assert set(q[0]) == {"id", "receivedAt", "callerId", "durationSec", "worked"}


async def test_a_message_has_its_script(client):
    m = (await client.get("/api/messages/m37")).json()
    assert "oxygen" in m["script"] and m["words"] > 100
    assert (await client.get("/api/messages/m99")).status_code == 404


async def test_lookup_by_name_phone_and_case(client):
    assert (await client.get("/api/lookup", params={"q": "Whitfield"})).json()[0]["id"] == "FBS-104227"
    assert (await client.get("/api/lookup", params={"q": "(865) 555-0190"})).json()[0]["name"] == "Eleanor Voss"
    assert (await client.get("/api/cases/311902")).json()["name"] == "Marcus Bell"


async def test_manual_entries_are_kept_and_mark_the_inbox(client):
    entry = {"callerName": "Eleanor Voss", "callbackNumber": "865-555-0190", "category": "Urgent hardship",
             "priority": 5, "disposition": "Escalate", "secondsSpent": 151}
    assert (await client.put("/api/entries/m37", json=entry)).status_code == 200
    assert (await client.get("/api/entries")).json()["m37"]["priority"] == 5
    assert next(m for m in (await client.get("/api/queue")).json() if m["id"] == "m37")["worked"]


async def test_working_the_queue_in_order(client):
    sim = (await client.get("/api/simulation", params={"mode": 0})).json()
    assert sim["order"][:3] == ["m01", "m02", "m03"]
    assert sim["urgentId"] == "m37"
    assert "14:00" <= sim["urgentFirstTouch"] <= "15:00"           # mid-afternoon: hours after the call
    assert sim["urgentWaitMin"] >= 180
    assert 8 <= sim["agentHours"] <= 12 and sim["unreached"] > 0    # one agent can't clear a day like this
    assert sim["obligationsMissed"] >= 2 and "m37:welfare" in sim["missed"]


async def test_assumptions_drive_the_numbers(client):
    base = (await client.get("/api/simulation")).json()["agentHours"]
    a = (await client.get("/api/assumptions")).json()
    await client.put("/api/assumptions", json={**a, "handleMin": 2.0, "callbackMin": 3.0})
    faster = (await client.get("/api/simulation")).json()
    await client.put("/api/assumptions", json=a)
    assert faster["agentHours"] < base and faster["urgentFirstTouch"] < "14:00"
