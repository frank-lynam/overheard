"""Tickets against a real hearthboard (0.2.0 or later: projects), started in the test: a proposal lands in the
proposed team's project, and an accept, a move and a decline are each read back. Uses HEARTHBOARD_SRC (or a
hearthboard checkout next to this repo) when hearthboard isn't installed; skipped when there's none."""

import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data.generator import seed
from overheard.workflow.sink import HearthboardSink

sys.path.insert(0, os.environ.get("HEARTHBOARD_SRC", str(Path(__file__).resolve().parents[2] / "hearthboard")))
hb = pytest.importorskip("hearthboard")
if getattr(hb, "SCHEMA_VERSION", 0) < 11:
    pytest.skip("needs hearthboard with projects (0.2.0 or later)", allow_module_level=True)

TEAMS = ["benefits-processing", "records", "portal-it", "congressional-affairs", "legal", "fraud", "outreach"]


@pytest.fixture(scope="module")
def board(tmp_path_factory):
    srv = hb.make_server("127.0.0.1", 0, tmp_path_factory.mktemp("board"))
    st = srv.store
    boss = st.add_user("supervisor", "human", "test")[1]
    agent = st.add_user("overheard", "agent", "test")[1]
    for t in TEAMS:
        st.create_project({"name": t.replace("-", " ").title(), "slug": t}, "supervisor")
        st.set_member(t, "overheard", "member", "supervisor")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", boss, agent
    srv.shutdown()


def act(url, token, method, path, body=None):
    req = urllib.request.Request(url + path, method=method, data=json.dumps(body or {}).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_accept_move_and_decline_are_read_back(board):
    url, boss, agent = board
    sink = HearthboardSink(url, agent)
    a, b, c = (sink.create("records", f"Problem {i}", "details", 2) for i in range(3))
    assert act(url, boss, "GET", f"/api/tickets/{a}")["project"] == "records"
    assert sink.decision(a, "records")["status"] == "proposed"
    act(url, boss, "POST", f"/api/tickets/{a}/accept")
    act(url, boss, "PATCH", f"/api/tickets/{b}", {"project": "legal"})
    act(url, boss, "POST", f"/api/tickets/{c}/decline")
    got = [sink.decision(x, "records") for x in (a, b, c)]
    assert [(d["status"], d["team"]) for d in got] == [("accepted", "records"), ("moved", "legal"), ("declined", "records")]
    assert all(d["decidedBy"] == "supervisor" for d in got)


async def test_overheard_files_its_tickets_there(board, tmp_path):
    url, boss, agent = board
    seed(tmp_path / "day.db", 2026)
    app = create_app(Settings(db_path=tmp_path / "day.db", workflow_url=url, workflow_token=agent))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
        made = []
        while not any(t["item_id"] == "m14" for t in made):
            made = (await c.post("/api/tickets/reveal", json={})).json()["made"]
            assert made
        t = made[0]
        on_board = act(url, boss, "GET", f"/api/tickets/{t['board_id']}")
        assert on_board["project"] == "records" and on_board["proposed"] == 1 and t["link"].endswith(t["board_id"])
        act(url, boss, "PATCH", f"/api/tickets/{t['board_id']}", {"project": "legal"})
        back = (await c.get(f"/api/tickets/{t['ticket_id']}")).json()
        assert back["status"] == "proposed"                                # until it's read back
        listed = (await c.get("/api/tickets")).json()
        mine = next(x for x in listed["tickets"] if x["ticket_id"] == t["ticket_id"])
        assert (mine["status"], mine["final_team"], mine["decided_by"]) == ("moved", "legal", "supervisor")
        assert (await c.post(f"/api/tickets/{t['ticket_id']}/decide", json={"action": "accept"})).status_code == 400
