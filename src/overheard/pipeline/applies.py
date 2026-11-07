"""Stage [D], applies triage: which of the agency's policies, programs, notices, outages and deadlines
(data/applicability.json) apply to a voicemail? Retrieval picks the closest few rules in force on the day (a rule
outside its validity window is never offered), then the LLM task applies_triage decides each, quoting the caller.
Plain code checks the quote: an "applies" whose words aren't in the transcript becomes "unsure", shown to a person
with its reason."""

from __future__ import annotations

import json
import re
from functools import cache
from importlib import resources

from overheard.data.models import Voicemail
from overheard.memory.embed import MockEmbeddingProvider, cosine

TOP_N = 3
MIN_SCORE = 0.08     # below this a rule isn't offered at all
KEYWORD_BOOST = 0.3  # a rule's own words in the transcript (and translations keep form numbers and codes)


@cache
def catalogue() -> list[dict]:
    return json.loads(resources.files("overheard.data").joinpath("applicability.json").read_text())["rules"]


def in_force(rule: dict, day: str) -> bool:
    return rule["valid_from"] <= day[:10] <= rule["valid_to"]


def rule_text(rule: dict) -> str:
    return " ".join([rule["name"], rule["description"], *rule["examples"]["applies"], *rule["keywords"]])


@cache
def _embedder() -> tuple[MockEmbeddingProvider, dict]:
    texts = [rule_text(r) for r in catalogue()]
    e = MockEmbeddingProvider(texts)
    return e, {r["id"]: e.embed(t) for r, t in zip(catalogue(), texts, strict=True)}


def find_quote(script: str, rule: dict) -> tuple[int, int] | None:
    """Where the first of the rule's own words appears in the transcript (case-insensitive, whole words)."""
    best = None
    for k in rule["keywords"]:
        m = re.search(r"(?<![\w-])" + re.escape(k) + r"(?![\w])", script, re.IGNORECASE)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.end())
    return best


def candidates(v: Voicemail, day: str, n: int = TOP_N) -> list[dict]:
    """The closest rules in force on the day, with their scores: similarity plus a boost for the rule's words."""
    e, vecs = _embedder()
    q = e.embed(v.script)
    scored = []
    for r in catalogue():
        if not in_force(r, day):
            continue
        s = cosine(q, vecs[r["id"]]) + (KEYWORD_BOOST if find_quote(v.script, r) else 0.0)
        if s >= MIN_SCORE:
            scored.append((round(s, 3), r))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [{**r, "score": s} for s, r in scored[:n]]


def truly_applies(v: Voicemail, rule: dict) -> bool:
    """The ground truth: the rule covers the message's root cause or one of its obligations."""
    t = v.truth
    return t.rootCause in rule.get("causes", []) or bool(set(t.obligations) & set(rule.get("obligations", [])))


def check(v: Voicemail, offered: list[dict], verdicts: list[dict]) -> list[dict]:
    """Keep one verdict per offered rule (anything else is dropped: never a rule that wasn't offered), and make the
    quote a span: an "applies" whose quote isn't in the transcript becomes "unsure"."""
    by = {r["id"]: r for r in offered}
    out, seen = [], set()
    for x in verdicts:
        r = by.get(x["rule_id"])
        if not r or x["rule_id"] in seen:
            continue
        seen.add(x["rule_id"])
        q = (x.get("quote") or "").strip()
        i = v.script.lower().find(q.lower()) if q else -1
        span = [i, i + len(q)] if i >= 0 else None
        verdict, reason = x["verdict"], x["reason"]
        if verdict == "applies" and not span:
            verdict, reason = "unsure", f"{reason} (but the words it quoted aren't in the message: check it)"
        out.append({"ruleId": r["id"], "name": r["name"], "scope": r["scope"], "verdict": verdict, "reason": reason,
                    "quote": v.script[span[0]:span[1]] if span else None, "span": span, "score": r["score"]})
    order = {"applies": 0, "unsure": 1, "does_not_apply": 2}
    return sorted(out, key=lambda a: (order[a["verdict"]], -a["score"]))


def _task(v: Voicemail, offered: list[dict]):
    from overheard.llm.tasks import TASKS
    plain = [{k: r[k] for k in ("id", "name", "description", "scope", "examples", "keywords", "causes")}
             | {"obligations": r.get("obligations", [])} for r in offered]
    return TASKS["applies_triage"].build(v, plain)


def _result(v: Voicemail, offered: list[dict], res) -> dict:
    return {"verdicts": check(v, offered, [x.model_dump() for x in res.data.verdicts]), "provenance": res.provenance}


async def triage(v: Voicemail, day: str, run) -> dict:
    """[D] for one voicemail. `run(task)` is an awaitable running an LLM task (provider, store: the app's)."""
    offered = candidates(v, day)
    return _result(v, offered, await run(_task(v, offered))) if offered else {"verdicts": [], "provenance": None}


def triage_sync(v: Voicemail, day: str, run) -> dict:
    """The same, with a `run(task)` that returns the result (the ticket desk's)."""
    offered = candidates(v, day)
    return _result(v, offered, run(_task(v, offered))) if offered else {"verdicts": [], "provenance": None}
