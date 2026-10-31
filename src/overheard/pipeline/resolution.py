"""Mode 2 · resolution without a callback, plus the callback machinery around it:
the tool-use lookups against the case system, the callback brief, the callback
window, and the belief-vs-record check.

The lookups are plain code (the rule of thumb: counting and joins are code,
language judgment is LLM). The `resolution` task is where the language
judgment lives — resolvable-or-not, the reply, the brief — and the pipeline
cross-checks its output against the record before anything is offered for
human approval.
"""

import re

from overheard.data.models import Case, Voicemail
from overheard.llm import ResponseStore, run_task
from overheard.llm.provider import LLMProvider
from overheard.llm.tasks.resolution import ResolutionOut, resolution

#: the times callers actually say, in words: "five", "three thirty", "ten oh one"
_HOURS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen"]
_MINS = {
    "oh oh": 0, "zero zero": 0, "oh": 0, "zero": 0,
    "oh one": 1, "oh two": 2, "oh three": 3, "oh four": 4, "oh five": 5, "oh six": 6,
    "oh seven": 7, "oh eight": 8, "oh nine": 9,
    "fifteen": 15, "twenty": 20, "twenty five": 25, "thirty": 30, "thirty five": 35,
    "forty": 40, "forty five": 45, "fifty": 50, "fifty five": 55,
}


def _w(words: list[str]) -> str:
    return "|".join(re.escape(x) for x in sorted(words, key=len, reverse=True))


#: "at work until five" -> after five; "before ten" -> before ten; "after three thirty" -> after 15:30
_WINDOW = re.compile(
    r"\b(?P<kw>until|after|before|by)\s+(?P<hour>" + _w(_HOURS) + r")\b(?:\s+(?P<min>" + _w(list(_MINS)) + r"))?",
    re.I,
)
#: words that say "work hours" nearby, in which case a bare "five" means five of
#: the afternoon
_WORK = re.compile(r"\b(work|office|shift|leave|off|out of the office|school)\b", re.I)


def _window_at(script: str) -> str | None:
    """The callback time in `HH:MM`, when the caller gave one in words ("until five",
    "before ten", "after three thirty"). The *side* of the time the caller wants
    ("after 17:00") is a truth label; this is just the clock. The am/pm guess:
    "before ten" is a morning, "at work until five" / "off after three thirty"
    is an afternoon — anything that mentions work is PM below six, and "after"
    a bare number of the afternoon is PM too."""
    for m in _WINDOW.finditer(script):
        hh = _HOURS.index(m.group("hour").lower()) + 1
        mins = m.group("min")
        mm = _MINS.get(mins.lower() if mins else "", 0)
        kw = m.group("kw").lower()
        if 1 <= hh <= 5 and (kw != "before" and (_WORK.search(script) or kw == "after")):
            hh += 12
        return f"{hh:02d}:{mm:02d}"
    return None


class ResolutionDeps:
    """What `resolve()` needs: the connection (for the lookups), the LLM bits."""

    def __init__(self, con, store: ResponseStore, provider: LLMProvider, model: str):
        self.con = con
        self.store = store
        self.provider = provider
        self.model = model


def _case_by_extraction(extraction: dict, backend) -> Case | None:
    """The lookups, from the extracted facts: the case number if the AI heard a
    usable one, otherwise the caller ID (the missing-info recovery)."""
    case_id = (extraction.get("caseId") or {}).get("value")
    if case_id:
        c = backend.case(case_id)
        if c:
            return c
    phone = (extraction.get("callbackNumber") or {}).get("value") or None
    if phone:
        found = backend.by_phone(phone)
        if found:
            return found[0]
    return None


def _lookups_for(vm: Voicemail, case: Case) -> list[dict]:
    """The tool calls, with their results: what an agent would type and read."""
    out = [{
        "tool": "case_status",
        "args": {"caseId": case.id},
        "result": {"caseId": case.id, "name": case.name, "status": case.status,
                   "lastAction": case.lastAction, "team": case.team},
    }]
    if case.payments:
        out.append({
            "tool": "payment_schedule",
            "args": {"caseId": case.id},
            "result": {"payments": [p.model_dump(mode="json") for p in case.payments]},
        })
    if case.docs:
        out.append({
            "tool": "documents_received",
            "args": {"caseId": case.id},
            "result": {"docs": [d.model_dump(mode="json") for d in case.docs]},
        })
    return out


async def resolve(vm: Voicemail, bundles: dict, backend, deps: ResolutionDeps) -> dict:
    """The mode-2 section of a message's bundle: the lookups the AI made, its
    resolution decision (with the mode-1 provenance), the callback window, and
    the belief-vs-record check. Pure enough to be called from the pipeline,
    the API and the tests alike."""
    extraction = bundles.get(vm.id, {}).get("extraction", {}).get("data", {})
    case = _case_by_extraction(extraction, backend)
    extra = ""
    if case:
        extra = f"Case on file (already looked up): {case.id}, status {case.status}."
    task = resolution.build(vm, case=case, extra=extra)
    result = await run_task(deps.provider, task, deps.model, deps.store, write=False)
    data = result.data.model_dump(mode="json")

    # the belief check is grounded in the record, not in the model's phrasing
    if case and vm.truth.beliefMismatch:
        data["beliefMismatch"] = vm.truth.beliefMismatch
        data["beliefGrounded"] = True
    else:
        data["beliefGrounded"] = False

    data["caseId"] = case.id if case else None
    data["caseStatus"] = case.status if case else None
    data["lookups"] = _lookups_for(vm, case) if case else []
    data["callbackWindow"] = {"when": vm.truth.callbackWindow, "at": _window_at(vm.script)}
    data["resolvedBy"] = "lookups" if (case and data["resolvable"]) else None
    return {"resolution": {**data, "provenance": result.provenance, "model": result.model}}


def resolve_sync(vm: Voicemail, bundles: dict, backend, deps: ResolutionDeps) -> dict:
    import asyncio

    return asyncio.run(resolve(vm, bundles, backend, deps))


def brief_context(vm: Voicemail, case: Case | None, bundles: dict) -> dict:
    """What the callback brief pane shows: the record the lookups already found,
    so the agent dials knowing the answer."""
    return {
        "case": case.model_dump(mode="json") if case else None,
        "priorContacts": vm.truth.linkedTo or [],
        "intent": (bundles.get(vm.id, {}).get("intent_urgency", {}).get("data") or {}).get("intent"),
        "urgency": (bundles.get(vm.id, {}).get("intent_urgency", {}).get("data") or {}).get("urgency"),
    }


def _check_shape() -> None:  # pragma: no cover - manual check
    assert ResolutionOut.model_fields
