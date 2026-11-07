"""Retroactive relevance, "Overlooked before today": once a problem is identified (by an analyst, or offered when
today's spike appears in Mode 2), find the past contacts in a look-back window that were that problem but were
overlooked: never ticketed (taken for something answered on the call), or ticketed to the wrong team.

  1. the definition: a description, a few examples, a look-back date, and the team that owns the problem
  2. retrieval: the window's contacts sharing a word with the definition, scored by similarity (mock embeddings)
  3. the overlooked ones: their recorded kind isn't a ticketed problem, or routing memory sent them elsewhere
  4. the LLM task retro_match confirms the strongest, with a reason
  5. dates, counts and the agent time they took (hours, from the archive's own handling times)

On demand only (POST /api/retro), never on every item."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from overheard.memory.embed import MockEmbeddingProvider, cosine, tokens
from overheard.memory.store import owner, teams_map

MIN_SIMILARITY = 0.08
MAX_CHECKED = 80        # the strongest candidates the LLM confirms
BATCH = 20              # contacts per retro_match call
LOOK_BACK_DAYS = 28


def words(text: str) -> set[str]:
    return {t for t in tokens(text) if "_" not in t and not t.startswith("type:")}


def suggest(incident: dict, members: list, today: str) -> dict:
    """A definition offered from today's spike: its title, a few callers' words, four weeks back, its team."""
    causes = sorted({m.truth.rootCause for m in members})          # what the members are, as the day's labels say
    team = owner(causes[0])[0] if causes else None
    examples = [m.script.replace("\n", " ") for m in sorted(members, key=lambda m: m.receivedAt)[:4]]
    card = incident["card"]
    return {"description": f"{card['title']}: {card.get('probableCause', '')}".strip(), "examples": examples,
            "since": (date.fromisoformat(today[:10]) - timedelta(days=LOOK_BACK_DAYS)).isoformat(),
            "until": today[:10], "team": team, "origin": "today's spike"}


def candidates(con: sqlite3.Connection, d: dict) -> list[dict]:
    """[2] and [3]: the window's contacts close to the definition that were overlooked, strongest first."""
    query = " ".join([d["description"], *d.get("examples", [])])
    want = words(query)
    rows = con.execute("SELECT id, at, root_cause, text, handle_min FROM contacts WHERE at >= ? AND at < ? "
                       "ORDER BY at, id", (d["since"], d["until"])).fetchall()
    near = [r for r in rows if words(r[3] or "") & want]                       # token prefilter
    routed = dict(con.execute("SELECT item_id, final_team FROM memory_items"))
    e = MockEmbeddingProvider([r[3] or "" for r in rows])
    q = e.embed(query)
    out = []
    for cid, at, cause, text, handle in near:
        s = cosine(q, e.embed(text or ""))
        if s < MIN_SIMILARITY:
            continue
        team, problem = owner(cause)
        went = routed.get(cid)
        if problem and (went is None or went == d.get("team")) and team == d.get("team"):
            continue                    # ticketed, to the right team: not overlooked
        why = "never ticketed" if not problem else f"ticketed to {went or team}"
        out.append({"id": cid, "at": at, "recordedAs": cause, "text": text, "handleMin": handle,
                    "similarity": round(s, 3), "overlooked": why, "matched": sorted(words(text or "") & want)})
    out.sort(key=lambda c: (-c["similarity"], c["id"]))
    return out[:MAX_CHECKED]


def search(con: sqlite3.Connection, d: dict, run) -> dict:
    """The whole search. `run(task)` runs an LLM task and returns its result (provider and store: the app's)."""
    from overheard.llm.tasks import TASKS
    cands = candidates(con, d)
    row = con.execute("SELECT value FROM meta WHERE key = 'overlooked'").fetchone()
    planted = set(json.loads(row[0])) if row else set()
    found, provenance = [], None
    for i in range(0, len(cands), BATCH):
        batch = cands[i:i + BATCH]
        items = [{"id": c["id"], "at": c["at"], "text": c["text"]} for c in batch]
        res = run(TASKS["retro_match"].build(d, items, [c["id"] for c in batch if c["id"] in planted]))
        provenance = res.provenance
        verdict = {m.id: m for m in res.data.matches}
        for c in batch:
            m = verdict.get(c["id"])
            if m and m.match:
                found.append({**c, "reason": m.reason})
    found.sort(key=lambda c: (c["at"], c["id"]))
    hours = sum(c["handleMin"] or 0 for c in found) / 60
    days = len({c["at"][:10] for c in found})
    first = found[0]["at"][:10] if found else None
    lead = (date.fromisoformat(d["until"]) - date.fromisoformat(first)).days if first else 0
    teams = teams_map()["teams"]
    return {"definition": d, "checked": len(cands), "provenance": provenance, "items": found,
            "summary": {"count": len(found), "days": days, "first": first, "last": found[-1]["at"][:10] if found else None,
                        "agentHours": round(hours, 1), "leadDays": lead,
                        "team": teams.get(d.get("team"), d.get("team"))}}
