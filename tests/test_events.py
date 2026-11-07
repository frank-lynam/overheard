"""Server-sent events: the bus carries events from worker threads to open streams; the ticket desk publishes an
`alert` for each code-word voicemail it reaches and a `ticket` when one is created or decided; the stream frames
them as SSE."""

import asyncio
import json
import threading

import httpx
import pytest

from overheard.api.events import Bus, frame
from overheard.app import create_app
from overheard.config import Settings
from overheard.data.generator import seed


def test_the_bus_carries_events_from_other_threads():
    async def main():
        bus = Bus()
        q = bus.subscribe()
        threading.Thread(target=bus.publish, args=("ticket", {"ticket_id": "T-m01"})).start()
        got = await asyncio.wait_for(q.get(), 5)
        bus.unsubscribe(q)
        bus.publish("ticket", {})                       # nobody listening: nothing happens
        return got, bus.listeners
    got, left = asyncio.run(main())
    assert got == ("ticket", {"ticket_id": "T-m01"}) and left == 0
    assert frame("alert", {"a": 1}) == 'event: alert\ndata: {"a": 1}\n\n'


@pytest.fixture
async def app_and_client(tmp_path):
    seed(tmp_path / "day.db", 2026)
    app = create_app(Settings(db_path=tmp_path / "day.db"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        yield app, c


async def test_the_desk_publishes_alerts_and_tickets(app_and_client):
    app, c = app_and_client
    seen = []
    app.state.events.publish = lambda kind, data: seen.append((kind, data))
    made = (await c.post("/api/tickets/reveal", json={"all": True})).json()["made"]
    alerts = (await c.get("/api/alerts")).json()["alerts"]
    queued = {q["id"] for q in (await c.get("/api/queue", params={"mode": 1})).json()}
    assert {d["item_id"] for k, d in seen if k == "alert"} == {a["id"] for a in alerts if a["id"] in queued}
    assert all(d["label"] and "safety" in d for k, d in seen if k == "alert")
    created = [d for k, d in seen if k == "ticket" and d["event"] == "created"]
    assert [d["ticket_id"] for d in created] == [t["ticket_id"] for t in made]
    t = made[0]
    await c.post(f"/api/tickets/{t['ticket_id']}/decide", json={"action": "move", "team": "records"})
    decided = [d for k, d in seen if k == "ticket" and d["event"] == "decided"]
    assert len(decided) == 1 and decided[0]["status"] == "moved" and decided[0]["final_team"] == "records"


async def test_the_stream_frames_events(app_and_client):
    app, c = app_and_client

    async def publish_soon():
        while not app.state.events.listeners:
            await asyncio.sleep(0.01)
        app.state.events.publish("ticket", {"ticket_id": "T-x", "event": "created"})
        app.state.events.publish("alert", {"item_id": "m37"})
    task = asyncio.create_task(publish_soon())
    r = await c.get("/api/events", params={"limit": 2})
    await task
    assert r.headers["content-type"].startswith("text/event-stream")
    blocks = [b for b in r.text.split("\n\n") if b.startswith("event:")]
    assert [b.split("\n")[0] for b in blocks] == ["event: ticket", "event: alert"]
    assert json.loads(blocks[0].split("data: ")[1]) == {"ticket_id": "T-x", "event": "created"}
