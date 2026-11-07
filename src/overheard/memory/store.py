"""The memory: past items with the team they were finally routed to, and the events that got them there (routings,
moves, declines, corrections). `overheard seed` builds it from the archive: a share of the problem contacts with a
routing decision, some planted misroutes a person later corrected, and a fifth held out to measure proposals by.
Today's decisions are added as they're read back (stage [H]), so they change later proposals.

Search is brute-force cosine over the routed items (a few thousand): plain Python, no numpy."""

from __future__ import annotations

import json
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files

from overheard.memory.embed import MockEmbeddingProvider, Vector, cosine

K = 8                    # neighbours a proposal looks at
MIN_SIMILARITY = 0.25    # below this, a past item says nothing about this one
MIN_CONFIDENCE = 0.5     # below this share of the evidence, the proposal is "unknown" (the ticket goes to general)
PERSON_TODAY = 5.0       # a person's decision today outweighs older routings: they just corrected it
ROUTED_SHARE = 8         # one in this many problem contacts in the archive has a routing decision
HOLDOUT = 0.2
AMBIGUOUS = 0.07         # past routings that ended with another team and stayed there (real history isn't tidy)


def doc(problem_type: str | None, text: str) -> str:
    """What's embedded: the problem's type (the problem check names it) as a label at full weight, and its wording.
    Retrieval matches the same kind of problem first, then similar wording, not the filler of a long voicemail."""
    return (f"type:{problem_type} " * 2 if problem_type else "") + text   # the type first, full weight, then the wording


@lru_cache(maxsize=1)
def teams_map() -> dict:
    return json.loads((files("overheard") / "data" / "teams.json").read_text())


def owner(cause: str) -> tuple[str | None, bool]:
    """(the team that owns a root cause, whether it's a problem a team must act on)."""
    t, problem = teams_map()["causes"].get(cause, [None, False])
    return t, problem


def build(con: sqlite3.Connection, seed_value: int) -> dict:
    """Write the seeded memory (inside the caller's transaction). Deterministic: same seed, same rows."""
    rng = random.Random(f"memory:{seed_value}")
    misroutes = teams_map()["misroutes"]
    rows = con.execute("SELECT id, at, root_cause, text FROM contacts ORDER BY id").fetchall()
    picked = [r for r in rows if owner(r[2])[1] and rng.randrange(ROUTED_SHARE) == 0]
    embed = MockEmbeddingProvider([doc(r[2], r[3]) for r in picked])
    teams = sorted(teams_map()["teams"])
    events = 0
    for cid, at, cause, text in picked:
        team = owner(cause)[0]
        if rng.random() < AMBIGUOUS:
            team = rng.choice([t for t in teams if t != team])
        holdout = rng.random() < HOLDOUT
        con.execute("INSERT INTO memory_items VALUES (?,?,?,?,?,?,?,?)",
                    (cid, text, json.dumps(embed.embed(doc(cause, text)), sort_keys=True), at, cause, team, "routed",
                     int(holdout)))
        wrong = misroutes.get(cause)
        if wrong and rng.random() < 0.35:   # first sent to the wrong team, then a person moved it
            con.execute("INSERT INTO memory_events VALUES (?,?,?,?,?)",
                        (f"{cid}:routing", cid, "routing", json.dumps({"team": wrong}), at))
            con.execute("INSERT INTO memory_events VALUES (?,?,?,?,?)",
                        (f"{cid}:move", cid, "move", json.dumps({"from": wrong, "to": team}), at))
            events += 2
        else:
            con.execute("INSERT INTO memory_events VALUES (?,?,?,?,?)",
                        (f"{cid}:routing", cid, "routing", json.dumps({"team": team}), at))
            events += 1
    return {"memory_items": len(picked), "memory_events": events}


@dataclass
class Item:
    item_id: str
    text: str
    vector: Vector
    created_at: str
    problem_type: str | None
    final_team: str | None
    holdout: bool
    by_person_today: bool = False


class Memory:
    """The routed items, loaded once; today's decisions added as they come (`record`)."""

    def __init__(self, con: sqlite3.Connection, today: str):
        self.con, self.today = con, today
        rows = con.execute("SELECT item_id, text, vector, created_at, problem_type, final_team, holdout "
                           "FROM memory_items ORDER BY item_id").fetchall()
        self.embedder = MockEmbeddingProvider([doc(r[4], r[1]) for r in rows if not r[0].startswith(("m", "j"))])
        self.items = {r[0]: Item(r[0], r[1], {int(k): v for k, v in json.loads(r[2]).items()}, r[3], r[4], r[5],
                                 bool(r[6]), r[3][:10] == today) for r in rows}

    def version(self) -> int:
        """Changes whenever a decision is recorded: proposals are cached by (item, memory version)."""
        return self.con.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]

    def neighbours(self, text: str, k: int = K, exclude: str | None = None,
                   holdout: bool = False) -> list[tuple[Item, float]]:
        q = self.embedder.embed(text)
        scored = [(it, cosine(q, it.vector)) for it in self.items.values()
                  if it.final_team and it.item_id != exclude and (holdout or not it.holdout)]
        scored = [(it, s) for it, s in scored if s >= MIN_SIMILARITY]
        scored.sort(key=lambda x: (-x[1], x[0].item_id))
        return scored[:k]

    def weigh(self, text: str, exclude: str | None = None) -> dict:
        """The evidence for a team proposal: the neighbours (plus today's decisions by people on the same kind of
        problem), each weighted by similarity and recency (a person's decision today counts PERSON_TODAY times), and
        each team's share of the weight."""
        today = date.fromisoformat(self.today)
        evidence, weight = [], {}
        found = self.neighbours(text, exclude=exclude)
        # A person's decision today on the same kind of problem is always evidence, however differently it was
        # worded: the problem check already judged it the same kind, and a fresh correction is the strongest
        # signal there is (in a templated archive, many near-identical old routings fill the K nearest otherwise).
        label = re.search(r"type:([a-z0-9-]+)", text.lower())
        if label:
            have = {it.item_id for it, _ in found}
            q = self.embedder.embed(text)
            found += [(it, max(cosine(q, it.vector), MIN_SIMILARITY)) for it in self.items.values()
                      if it.by_person_today and it.final_team and it.problem_type == label.group(1)
                      and it.item_id not in have and it.item_id != exclude]
        for it, sim in found:
            age = (today - date.fromisoformat(it.created_at[:10])).days
            w = sim * (0.5 ** (max(age, 0) / 365)) * (PERSON_TODAY if it.by_person_today else 1.0)
            evidence.append({"ref": it.item_id, "team": it.final_team, "similarity": round(sim, 3), "weight": round(w, 3),
                             "text": it.text[:160], "when": it.created_at[:10], "today": it.by_person_today})
            weight[it.final_team] = weight.get(it.final_team, 0.0) + w
        total = sum(weight.values())
        shares = {t: round(w / total, 3) for t, w in sorted(weight.items(), key=lambda x: -x[1])} if total else {}
        return {"evidence": evidence, "shares": shares}

    def record(self, event_id: str, item_id: str, kind: str, payload: dict, created_at: str,
               text: str | None = None, team: str | None = None, problem_type: str | None = None) -> bool:
        """Stage [H]: a decision read back. Idempotent on event_id. Returns whether it was new."""
        cur = self.con.execute("INSERT OR IGNORE INTO memory_events VALUES (?,?,?,?,?)",
                               (event_id, item_id, kind, json.dumps(payload, sort_keys=True), created_at))
        if not cur.rowcount:
            return False
        if team is not None or kind == "decline":
            final = None if kind == "decline" else team
            vec = self.embedder.embed(doc(problem_type, text or ""))
            self.con.execute(
                "INSERT INTO memory_items VALUES (?,?,?,?,?,?,?,0) ON CONFLICT(item_id) DO UPDATE SET "
                "final_team = excluded.final_team, disposition = excluded.disposition",
                (item_id, text or "", json.dumps(vec, sort_keys=True), created_at, problem_type, final,
                 "declined" if kind == "decline" else "routed"))
            self.items[item_id] = Item(item_id, text or "", vec, created_at, problem_type, final, False,
                                       created_at[:10] == self.today)
        self.con.commit()
        return True

    def holdout_accuracy(self) -> dict:
        """Proposals for the held-out fifth, from the rest of the memory, against where each really went."""
        right = total = unknown = 0
        for it in self.items.values():
            if not it.holdout or not it.final_team:
                continue
            total += 1
            w = self.weigh(doc(it.problem_type, it.text), exclude=it.item_id)
            top = next(iter(w["shares"].items()), (None, 0.0))
            if top[1] < MIN_CONFIDENCE:
                unknown += 1
            elif top[0] == it.final_team:
                right += 1
        return {"heldOut": total, "right": right, "unknown": unknown,
                "accuracy": round(right / total, 3) if total else 0.0}
