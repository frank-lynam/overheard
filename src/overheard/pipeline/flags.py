"""Mode 2 · deadline-bound request detection: the LLM's obligation flags, a
keyword backstop for recall, and the agency policy that turns a flag into a
deadline clock.

High recall matters more than precision here (a wrongly flagged message costs
a human a look; a missed one costs the caller a deadline), so the keyword
backstop runs *on top of* the LLM's flags and can only add, never remove.
"""

import re
from datetime import date, timedelta

from overheard.data.models import Obligation

#: The agency's policy on how quickly each kind of deadline-bound request must
#: be handled, in business days from when the message was received. This is
#: owned by the agency, not set by the model (a real deployment reads it from
#: config; the demo ships the design doc's numbers).
POLICY: dict[Obligation, int] = {
    "congressional": 5,   # a congressional office is waiting on a written answer
    "records": 20,        # a records request, e.g. an informal FOIA
    "legal": 2,           # the caller named a date in the message
    "welfare": 1,         # someone's day is at risk
    "discrimination": 10,
}

#: The keyword backstop. Each pattern is a family of ways a caller might mean
#: the thing without naming it: a senator's caseworker, "everything you have on
#: her", "my attorney", a shut-off and a fifty-year-old. `evidence` is the
#: human-readable note the backstop attached it with.
_CONG = r"\b(member of congress|congresswoman|congressman|congress|senator(?!ate)|senate|representative|caseworker)\b"
_RECORDS = (r"\b(FOIA|records request|copies of (?:everything|any|all)\b"
            r"|all the letters you've sent|everything you have on)")
_LEGAL = (r"\b(my attorney|attorney|lawyer|legal action|sue|lawsuit"
          r"|in writing by|on the twelfth|by the twentieth)\b")
_WELFARE = (r"\b(shut off|shut-off|utility|electric company"
            r"|power on (?:friday|monday|tuesday)|lives alone"
            r"|hasn't been eating|confused, he didn't know what day"
            r"|seventy(-| )eight|eighty(-| )three)\b")
_DISC = (r"\b(discriminat\w+|treated (?:me |us )?differently"
         r"|only (?:black|latin\w+|asian|white) (?:callers|applicants))\b")

_BACKSTOP: list[tuple[Obligation, re.Pattern[str], str]] = [
    ("congressional", re.compile(_CONG, re.I), "a mention of a member of Congress or their office"),
    ("records", re.compile(_RECORDS, re.I), "a request for the record on file"),
    ("legal", re.compile(_LEGAL, re.I), "a lawyer or a legal deadline in the caller's own words"),
    ("welfare", re.compile(_WELFARE, re.I), "a welfare or safety concern"),
    ("discrimination", re.compile(_DISC, re.I), "a discrimination complaint"),
]


def backstop(script: str) -> list[dict]:
    """What the keyword rules see in the script, on their own: a list of
    `{'kind', 'evidence'}` — one per family that fires, regardless of the LLM."""
    out = []
    for kind, pattern, why in _BACKSTOP:
        m = pattern.search(script)
        if m:
            out.append({"kind": kind, "evidence": why})
    return out


def obligations_of(script: str, ai_obligations: list[str]) -> list[dict]:
    """The LLM's flags plus the backstop: every obligation is kept, a backstop
    hit the LLM missed is added (marked `source: 'keyword'`), and the clock
    is computed for each. Duplicate kinds are merged, LLM first."""
    seen: dict[str, dict] = {}
    for kind in ai_obligations:
        if kind in POLICY:
            seen[kind] = {"kind": kind, "source": "llm", "evidence": "the intent/urgency task flagged it"}
    for hit in backstop(script):
        d = seen.setdefault(hit["kind"], {"kind": hit["kind"], "source": "keyword", "evidence": hit["evidence"]})
        d["source"] = "keyword" if d["source"] == "keyword" else "llm"  # LLM evidence wins in the note
    return [d for d in seen.values()]


def _add_business_days(d: date, n: int) -> date:
    """`n` business days after `d` (skipping Saturdays and Sundays)."""
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def deadline_due(received: date, kind: Obligation) -> str:
    """The clock, per the agency policy: the last day the request can be handled
    without missing the deadline. `YYYY-MM-DD`."""
    return _add_business_days(received, POLICY[kind]).isoformat()


def deadline_at(received: str, kind: Obligation) -> str:
    """Same, from the message's `receivedAt` string (`YYYY-MM-DDTHH:MM:SS...`)."""
    return deadline_due(date.fromisoformat(received[:10]), kind)
