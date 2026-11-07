"""Stage [B], the junk filter: robocalls, scams, silence and pocket dials kept out of the human queue, still counted,
with an audit trail. Rules first (plain code); then the LLM task `junk_classify` for the rest. `unsure` always goes
to a person, and a safety code word skips the filter altogether: missing a real problem is worse than letting junk
through. A person can reopen anything filtered."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from importlib.resources import files

from overheard.data.models import Voicemail


@dataclass(frozen=True)
class JunkRules:
    blocked_numbers: frozenset[str]
    min_words: int
    same_script_from: int
    scripted_phrases: tuple[str, ...]

    @classmethod
    def load(cls) -> JunkRules:
        d = json.loads((files("overheard") / "data" / "junk_rules.json").read_text())
        return cls(frozenset(d["blocked_numbers"]), int(d["min_words"]), int(d["same_script_from"]),
                   tuple(p.lower() for p in d["scripted_phrases"]))


def _norm(script: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", script.lower()).split())


def callers_per_script(vms: list[Voicemail]) -> dict[str, int]:
    """How many different numbers left each (normalised) transcript today."""
    seen: dict[str, set[str]] = defaultdict(set)
    for v in vms:
        seen[_norm(v.script)].add(v.callerId)
    return {k: len(v) for k, v in seen.items()}


def rule_for(v: Voicemail, rules: JunkRules, per_script: dict[str, int]) -> tuple[str, str] | None:
    """(rule id, reason) if a rule calls it junk, else None (then the LLM judges it)."""
    words = re.sub(r"\([^)]*\)", " ", v.script).split()          # "(silence)", "(a click)": not words said
    if len(words) < rules.min_words:
        return "too-short", "Silence, a click or a few sounds: nobody left a message."
    if v.callerId in rules.blocked_numbers:
        return "blocked-number", "The number is on the blocked list."
    n = per_script.get(_norm(v.script), 0)
    if n >= rules.same_script_from:
        return "same-script", f"The same recording came from {n} different numbers today."
    low = v.script.lower()
    hit = next((p for p in rules.scripted_phrases if p in low), None)
    if hit:
        return "scripted", f"A known robocall phrase: “{hit}”."
    return None


def decide(v: Voicemail, safety: bool, rules: JunkRules, per_script: dict[str, int], classify) -> dict:
    """The junk decision for one voicemail: {"disposition": "filtered" | "queued", "reason", "decidedBy", "verdict"}.
    `classify(v)` runs the LLM task and returns (verdict, reason, provenance)."""
    if safety:
        return {"disposition": "queued", "reason": "A safety code word: never filtered.", "decidedBy": "safety",
                "verdict": "not_junk"}
    rule = rule_for(v, rules, per_script)
    if rule:
        return {"disposition": "filtered", "reason": rule[1], "decidedBy": f"rule:{rule[0]}", "verdict": "junk"}
    verdict, reason, provenance = classify(v)
    return {"disposition": "filtered" if verdict == "junk" else "queued", "reason": reason,
            "decidedBy": "llm" if provenance != "fallback" else "fallback", "verdict": verdict}
