"""Tickets, stages [C] to [H]: each problem voicemail becomes one ticket in the workflow system, owned by the team
routing memory proposes; the human decision read back goes into the memory, and changes later proposals.

  [C] problem check (LLM problem_classify): not a problem, no ticket
  [D] applies triage (pipeline/applies.py): the rules in force that fit, quoted in the ticket
  [E] team proposal: routing memory's evidence (memory/store.py), then the LLM team_propose; below the threshold,
      "unknown", and the ticket goes to general
  [F] the ticket, sent to the sink (workflow/sink.py): the proposed team's project
  [G] the decision, read back: accepted, moved to another team, or declined
  [H] memory updated (idempotent), so the next similar problem is proposed where people sent this one

Voicemails are revealed in arrival order, and each proposal is worked out at its reveal, from the memory as it
stands then: that's what lets a move at 10:15 change the proposal for a call at 10:30. An outage's callers share
one ticket, and so do a repeat caller's messages."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable

from overheard.data.models import Voicemail
from overheard.memory.store import MIN_CONFIDENCE, Memory, doc, teams_map
from overheard.pipeline.applies import triage_sync

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket_units (unit_id TEXT PRIMARY KEY, item_id TEXT, item_ids TEXT, is_problem INTEGER,
  problem_type TEXT, statement TEXT, confidence REAL, reasons TEXT, revealed_at TEXT);
CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, item_id TEXT, item_ids TEXT, created_at TEXT,
  summary TEXT, statement TEXT, problem_type TEXT, problem_confidence REAL, proposed_team TEXT, team_confidence REAL,
  evidence TEXT, priority INTEGER, filed_in TEXT, board_id TEXT, status TEXT, final_team TEXT, final_assignee TEXT,
  decided_by TEXT, decided_at TEXT);
"""


def _brief(t: dict) -> dict:
    return {k: t[k] for k in ("ticket_id", "item_id", "summary", "status", "proposed_team", "final_team", "filed_in")}


class Desk:
    """One per app. `run(task)` runs an LLM task (provider, store and provenance are the app's); the sink is mock
    or hearthboard. Everything goes through one lock: tickets, memory and the sink are shared state."""

    def __init__(self, path, today: str, sink_factory: Callable[[sqlite3.Connection], object], run: Callable,
                 notify: Callable[[str, dict], None] | None = None):
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.executescript(SCHEMA)
        self.memory = Memory(self.con, today)
        self.sink = sink_factory(self.con)
        self.run = run
        self.notify = notify or (lambda kind, data: None)   # server-sent events: "alert", "ticket"
        self.lock = threading.RLock()
        self._accuracy: dict | None = None

    # --- the day's units: one per problem candidate (an outage or a repeat caller is one)
    @staticmethod
    def units(vms: list[Voicemail], day: dict) -> list[dict]:
        by = {v.id: v for v in vms}
        taken, out = set(), []
        for inc in day.get("incidents") or []:
            members = [m for m in inc["members"] if m in by]
            if members:
                lead = min(members, key=lambda m: (by[m].receivedAt, m))
                out.append({"unit_id": lead, "item_id": lead, "item_ids": sorted(members),
                            "incident": inc["card"]["title"]})
                taken |= set(members)
        for rep in (day.get("repeats") or {}).values():
            members = [m for m in rep["members"] if m in by and m not in taken]
            if members:
                out.append({"unit_id": members[0], "item_id": members[0], "item_ids": members, "incident": None})
                taken |= set(members)
        out += [{"unit_id": v.id, "item_id": v.id, "item_ids": [v.id], "incident": None} for v in vms if v.id not in taken]
        return sorted(out, key=lambda u: (by[u["item_id"]].receivedAt, u["item_id"]))

    def done_units(self) -> set[str]:
        return {r[0] for r in self.con.execute("SELECT unit_id FROM ticket_units")}

    # --- reveal: the next unit in arrival order, through [C], [E], [F]
    def reveal(self, units: list[dict], vms: dict[str, Voicemail], alerts: dict[str, dict],
               all_: bool = False) -> list[dict]:
        """Work through the units not revealed yet, until one makes a ticket (or all of them, with all_). Returns
        the tickets made."""
        made = []
        with self.lock:
            done = self.done_units()
            for u in units:
                if u["unit_id"] in done:
                    continue
                for i in u["item_ids"]:                 # a code word: the voicemail has reached the desk
                    if alerts.get(i):
                        a, w = alerts[i], vms[i]
                        self.notify("alert", {"item_id": i, "receivedAt": w.receivedAt, "callerId": w.callerId,
                                              **{k: a[k] for k in ("category", "label", "priority", "safety")}})
                t = self._reveal_one(u, vms[u["item_id"]], alerts.get(u["item_id"]))
                if t:
                    made.append(t)
                    if not all_:
                        break
        return made

    def _reveal_one(self, u: dict, v: Voicemail, alert: dict | None) -> dict | None:
        from overheard.llm.tasks import TASKS
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        p = self.run(TASKS["problem_classify"].build(v)).data
        self.con.execute("INSERT INTO ticket_units VALUES (?,?,?,?,?,?,?,?,?)",
                         (u["unit_id"], u["item_id"], json.dumps(u["item_ids"]), int(p.is_problem), p.problem_type,
                          p.statement, p.confidence, json.dumps(p.reasons), now))
        if not p.is_problem:
            self.con.commit()
            return None
        weighed = self.memory.weigh(doc(p.problem_type, p.statement))             # [E] from memory as it stands
        team = self.run(TASKS["team_propose"].build(p.problem_type, p.statement, weighed)).data
        known = team.proposed_team in teams_map()["teams"] and team.confidence >= MIN_CONFIDENCE
        proposed = team.proposed_team if known else "unknown"
        filed_in = proposed if known else teams_map()["general"]
        ids = set(team.evidence) & {e["ref"] for e in weighed["evidence"]}       # only ids that are really there
        evidence = [e for e in weighed["evidence"] if e["ref"] in ids] or weighed["evidence"][:3]
        n = len(u["item_ids"])
        line = p.statement.removeprefix("The caller's problem: ").rstrip(".")
        what = f"{u['incident']} ({n} callers)" if u.get("incident") else line[:1].upper() + line[1:]
        summary = (what + (f" · {n} messages from one caller" if n > 1 and not u.get("incident") else ""))[:190]
        priority = 1 if alert else 2
        applies = [a for a in triage_sync(v, v.receivedAt[:10], self.run)["verdicts"]               # [D]
                   if a["verdict"] != "does_not_apply"]
        board_id = self.sink.create(filed_in, summary, self.description(u, p, proposed, team.confidence, evidence,
                                                                            alert, applies), priority)   # [F]
        tid = f"T-{u['unit_id']}"
        self.con.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (tid, u["item_id"], json.dumps(u["item_ids"]), now, summary, p.statement, p.problem_type,
                          p.confidence, proposed, team.confidence, json.dumps(evidence), priority, filed_in, board_id,
                          "proposed", None, None, None, None))
        self.con.commit()
        t = self.ticket(tid)
        self.notify("ticket", {"event": "created", **_brief(t)})
        return t

    @staticmethod
    def description(u, p, proposed, conf, evidence, alert, applies=()) -> str:
        teams = teams_map()["teams"]
        lines = [f"Problem: {p.statement} ({p.problem_type}, confidence {p.confidence:.2f})", "",
                 f"Proposed team: {teams.get(proposed, 'unknown: filed in general')} (confidence {conf:.2f}).",
                 "Why: similar past problems went there:"]
        lines += [f"- {e['ref']} ({e['when']}): {e['text']} -> {e['team']}" for e in evidence[:5]] or ["- (none close)"]
        if applies:
            lines += ["", "Applies:"] + [f"- {a['name']}: {a['verdict'].replace('_', ' ')}. {a['reason']}"
                                         + (f" (heard: \"{a['quote']}\")" if a["quote"] else "") for a in applies]
        if alert:
            lines += ["", f"Code words: {', '.join(h['said'] for h in alert['hits'])} ({alert['label']})"]
        more = f" and {len(u['item_ids']) - 1} more" if len(u["item_ids"]) > 1 else ""
        lines += ["", f"Overheard item {u['item_id']}{more}. Filed by Overheard as a proposal: accept it, move it to "
                  "the team it belongs to, or decline it."]
        return "\n".join(lines)

    # --- [G] and [H]: decisions read back, into the memory
    def refresh(self) -> int:
        """Read back the decisions on open tickets; each new one goes into the memory. Returns how many changed."""
        changed = 0
        with self.lock:
            for r in self.con.execute("SELECT ticket_id, board_id, filed_in, item_id, statement, problem_type "
                                      "FROM tickets WHERE status = 'proposed'").fetchall():
                tid, board_id, filed_in, item_id, statement, ptype = r
                try:
                    d = self.sink.decision(board_id, filed_in)
                except Exception:          # the board is down: try again next time
                    continue
                if d["status"] == "proposed":
                    continue
                at = d["decidedAt"] or time.strftime("%Y-%m-%dT%H:%M:%S")
                # into the memory on the demo's day (its time of day kept): a decision made now is today's, for the
                # recency weight, and the evidence a later proposal is shown doesn't depend on the wall clock
                mem_at = f"{self.memory.today}T{at[11:19] or '12:00:00'}"
                self.con.execute("UPDATE tickets SET status = ?, final_team = ?, final_assignee = ?, decided_by = ?, "
                                 "decided_at = ? WHERE ticket_id = ?",
                                 (d["status"], None if d["status"] == "declined" else d["team"], d["assignee"],
                                  d["decidedBy"], at, tid))
                kind = {"accepted": "routing", "done": "routing", "moved": "move", "declined": "decline"}[d["status"]]
                payload = {"team": d["team"]} if kind == "routing" else {"from": filed_in, "to": d["team"]} \
                    if kind == "move" else {}
                self.memory.record(f"{tid}:{kind}", item_id, kind, payload, mem_at, text=statement,
                                   team=None if kind == "decline" else d["team"], problem_type=ptype)
                changed += 1
                self.con.commit()
                self.notify("ticket", {"event": "decided", **_brief(self.ticket(tid))})
            self.con.commit()
        return changed

    # --- reads
    def ticket(self, tid: str) -> dict | None:
        cur = self.con.execute("SELECT * FROM tickets WHERE ticket_id = ?", (tid,))
        r = cur.fetchone()
        if not r:
            return None
        t = dict(zip([c[0] for c in cur.description], r, strict=True))
        t["item_ids"], t["evidence"] = json.loads(t["item_ids"]), json.loads(t["evidence"])
        t["link"] = self.sink.link(t["board_id"])
        t["sink"] = self.sink.name
        return t

    def tickets(self) -> list[dict]:
        ids = [r[0] for r in self.con.execute("SELECT ticket_id FROM tickets ORDER BY created_at, ticket_id")]
        return [self.ticket(i) for i in ids]

    def accuracy(self) -> dict:
        """Proposals for the held-out fifth of the seeded routings (worked out once)."""
        if self._accuracy is None:
            with self.lock:
                self._accuracy = self.memory.holdout_accuracy()
        return self._accuracy
