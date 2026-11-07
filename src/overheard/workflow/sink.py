"""Stage [F], sending a ticket, and [G], reading the human decision back. A `WorkflowSink` is the seam:

- `MockWorkflowSink`: a local table, for tests and offline runs. Overheard's own tickets panel gives the Accept, Move
  and Decline buttons, so the learning loop works with no board running.
- `HearthboardSink`: hearthboard's HTTP API, as Overheard's own agent user. An agent's ticket is a proposal: it lands
  in the proposed team's project (general when unknown), and that team accepts it, moves it to the team it belongs
  to, or declines it. hearthboard has no webhooks, so the decision is read back by polling the ticket.

A decision is {"status": proposed | accepted | moved | declined | done, "team", "assignee", "decidedBy",
"decidedAt"}."""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from typing import Protocol


class WorkflowSink(Protocol):
    name: str

    def create(self, project: str, title: str, description: str, priority: int) -> str: ...

    def decision(self, board_id: str, filed_in: str) -> dict: ...

    def link(self, board_id: str) -> str | None: ...


class MockWorkflowSink:
    """Tickets in a local table; people decide with the console's own buttons (`decide`)."""

    name = "mock"

    def __init__(self, con: sqlite3.Connection):
        self.con = con
        con.execute("CREATE TABLE IF NOT EXISTS mock_board (board_id TEXT PRIMARY KEY, project TEXT, title TEXT, "
                    "description TEXT, priority INTEGER, status TEXT, assignee TEXT, decided_by TEXT, decided_at TEXT)")
        con.commit()

    def create(self, project: str, title: str, description: str, priority: int) -> str:
        n = self.con.execute("SELECT COUNT(*) FROM mock_board").fetchone()[0] + 1
        board_id = f"MB-{n:04d}"
        self.con.execute("INSERT INTO mock_board VALUES (?,?,?,?,?,?,?,?,?)",
                         (board_id, project, title, description, priority, "proposed", None, None, None))
        self.con.commit()
        return board_id

    def decide(self, board_id: str, action: str, team: str | None, by: str, assignee: str | None = None) -> None:
        if action not in ("accept", "move", "decline"):
            raise ValueError("action is accept, move or decline")
        row = self.con.execute("SELECT project FROM mock_board WHERE board_id = ?", (board_id,)).fetchone()
        if not row:
            raise KeyError(board_id)
        project = team if action == "move" and team else row[0]
        status = {"accept": "accepted", "move": "accepted", "decline": "declined"}[action]
        self.con.execute("UPDATE mock_board SET project = ?, status = ?, assignee = ?, decided_by = ?, decided_at = ? "
                         "WHERE board_id = ?", (project, status, assignee, by, time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                board_id))
        self.con.commit()

    def decision(self, board_id: str, filed_in: str) -> dict:
        r = self.con.execute("SELECT project, status, assignee, decided_by, decided_at FROM mock_board WHERE board_id = ?",
                             (board_id,)).fetchone()
        status = r[1]
        if status == "accepted" and r[0] != filed_in:
            status = "moved"
        return {"status": status, "team": r[0], "assignee": r[2], "decidedBy": r[3], "decidedAt": r[4]}

    def link(self, board_id: str) -> str | None:
        return None


class HearthboardSink:
    """hearthboard's API, as Overheard's agent user (a member of every project it files into)."""

    name = "hearthboard"

    def __init__(self, url: str, token: str, timeout: float = 10.0):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"hearthboard {method} {path}: {e.code} {e.read()[:300]!r}") from None

    def create(self, project: str, title: str, description: str, priority: int) -> str:
        # Agents file proposals into the backlog; a human of that team accepts, moves or declines it.
        t = self._call("POST", "/api/tickets", {"title": title[:199], "description": description, "status": "backlog",
                                                "priority": priority, "project": project})
        return t["id"]

    def decision(self, board_id: str, filed_in: str) -> dict:
        t = self._call("GET", f"/api/tickets/{board_id}")
        events = t.get("events") or []
        last = lambda *fields: next((e for e in reversed(events) if e["field"] in fields), None)   # noqa: E731
        if t.get("declined"):
            e, status = last("declined"), "declined"
        elif t.get("project") != filed_in:           # moved to another team (it may still be a proposal there)
            e, status = last("project"), "moved"
        elif t.get("proposed"):
            e, status = None, "proposed"
        elif t.get("status") == "done" and not t.get("cancelled"):
            e, status = last("accepted", "status"), "done"
        else:
            e, status = last("accepted"), "accepted"
        return {"status": status, "team": t.get("project"), "assignee": t.get("assignee"),
                "decidedBy": e["actor"] if e else None,
                "decidedAt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(e["at"])) if e else None}

    def link(self, board_id: str) -> str | None:
        return f"{self.url}/t/{board_id}"
