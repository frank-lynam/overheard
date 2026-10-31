"""MockProvider: built from the message's ground truth, with a seeded share of mistakes.

`Task.context` carries the message's truth labels (JSON); the mock builds a
plausible response from them without touching the database or the network, so
mock mode needs no hand-written fixtures and the scoreboard's accuracy stays
honest offline (about 94%). The context is NOT part of the prompt sent to a
live host. The same task always gets the same answer: the mistakes come from
a PRNG seeded on the task text.
"""

import json
import random
import re
from typing import Any

from overheard.llm.provider import LLMProvider, Task

ACCURACY = 0.94
ES = 0.13  # the archive's Spanish share: how often a Spanish caller is in the mock's training "memory"
# A wrong intent is almost always "looks like a status call"
WRONG_INTENT = "status_payment"
SENTIMENTS = ["calm", "mildly frustrated", "frustrated", "worried", "anxious"]
WORRY = re.compile(r"worried|anxious|scared|afraid|urgent|asap|right away|can't make rent|no food|losing our|due date", re.I)
ANGRY = re.compile(r"angry|frustrat|fed up|again and again|what a mess|ridiculous|unbelievable|five times|three times", re.I)


def _ctx(task: Task) -> dict[str, Any] | None:
    if not task.context:
        return None
    try:
        return json.loads(task.context)
    except json.JSONDecodeError:
        return None


def _script(task: Task) -> str:
    return task.user


def _wrong(rng: random.Random) -> bool:
    return rng.random() > ACCURACY


def _summary(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    gist = t.get("englishGist") or t.get("intent", "a call about an account").capitalize() + " call"
    text = gist if gist.endswith(".") else gist + "."
    if t.get("callerName"):
        text = f"{t['callerName']}: {text}"
    if _wrong(rng):
        return {"summary": text[: max(30, len(text) // 2)].rstrip()}  # an incomplete summary
    return {"summary": text}


def _extraction(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    out = {
        "callerName": t.get("callerName"),
        "callbackNumber": t.get("callbackNumber"),
        "caseId": t.get("caseId"),
        "caseNumberSaid": bool(t.get("caseNumberSaid", True)),
    }
    if _wrong(rng):
        if out["caseId"] is not None:
            out["caseId"] = None  # heard it, wrote it down wrong, dropped it
        elif out["callerName"]:
            out["callerName"] = out["callerName"].split()[0]  # first name only
        elif out["callbackNumber"]:
            out["callbackNumber"] = out["callbackNumber"][:-1] + "0"  # last digit off
    return out


def _intent(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    out = {"intent": t.get("intent", "other"), "urgency": int(t.get("urgency", 2))}
    if _wrong(rng):
        if rng.random() < 0.5:
            out["intent"] = WRONG_INTENT
        else:
            out["urgency"] = max(1, min(5, out["urgency"] + (1 if rng.random() < 0.5 else -1)))
    return out


def _translation(task: Task, rng: random.Random, t: dict[str, Any], script: str) -> dict:
    lang = (t.get("lang") or "en").split("-")[0]
    if lang == "en":
        return {"translated": False, "text": script, "sourceLang": "en"}
    gist = t.get("englishGist")
    if gist is None and rng.random() > ES:  # the mock's Spanish memory is spotty for the rest
        return {"translated": False, "text": "", "sourceLang": lang}
    if _wrong(rng):
        return {"translated": True, "text": (gist or "I...")[: max(20, len(gist or "") // 2)] + "...", "sourceLang": lang}
    return {"translated": True, "text": gist or "", "sourceLang": lang}


def _sentiment(task: Task, rng: random.Random, t: dict[str, Any], script: str) -> dict:
    score = 1 if re.search(r"please|just wanted|hope|kindly", script, re.I) else 0
    if WORRY.search(script):
        score += 1
    if ANGRY.search(script):
        score += 1
    level = max(0, min(len(SENTIMENTS) - 1, 1 + score))  # baseline: people calling are rarely "calm"
    sentiment = SENTIMENTS[level]
    if _wrong(rng):
        sentiment = SENTIMENTS[max(0, min(len(SENTIMENTS) - 1, level + (1 if rng.random() < 0.5 else -1)))]
    return {"sentiment": sentiment, "escalation": "follow-up" if score >= 1 and rng.random() < 0.3 else "standard"}


def _draft(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    name = (t.get("callerName") or "there").split()[0]
    case = t.get("caseId") or "your case"
    intent = t.get("intent", "other")
    bits = [f"Hi {name}, this is the Federal Benefits Service Center calling about {case}. "]
    if intent in ("status_payment",):
        bits.append("I want to follow up on the payment you asked about.")
    elif intent in ("status_document", "form_question"):
        bits.append("I want to follow up on the document you sent.")
    elif intent in ("portal_access",):
        bits.append("I want to follow up on the trouble you're having signing in to the portal.")
    else:
        bits.append("I'm calling to follow up on your last message.")
    if t.get("callbackNumber"):
        bits.append(f" Please let me know if {t['callbackNumber']} is still the best number to reach you at.")
    bits.append(" Thank you for your patience.")
    if _wrong(rng):
        text = "".join(bits[:2]) + " ... I'll let my supervisor look into it."  # a generic, unhelpful draft
    else:
        text = "".join(bits)
    return {"text": text, "tone": "polite", "signsOff": True}


def _generic(task: Task, rng: random.Random, script: str) -> dict:
    """No context (a hand-built task): a deterministic plausible answer from the text alone."""
    head = script[:180].strip()
    if task.name == "summary":
        return {"summary": head + ("..." if len(script) > len(head) else "")}
    if task.name == "extraction":
        case = re.search(r"F B S[\s ]*([0-9]{4,7})", script, re.I)
        return {"callerName": None, "callbackNumber": None, "caseId": f"FBS-{case.group(1)}" if case else None,
                "caseNumberSaid": bool(case)}
    if task.name == "intent_urgency":
        intent = "other"
        if re.search(r"congress", script, re.I):
            intent = "congressional"
        elif re.search(r"FOIA|records request", script, re.I):
            intent = "records_request"
        elif re.search(r"portal|sign(ing)? in|password", script, re.I):
            intent = "portal_access"
        elif re.search(r"payment|pay", script, re.I):
            intent = "status_payment"
        return {"intent": intent, "urgency": 3 if re.search(r"urgent|asap|right away", script, re.I) else 2}
    if task.name == "translation":
        return {"translated": False, "text": head, "sourceLang": "en"}
    if task.name == "sentiment":
        return {"sentiment": "calm", "escalation": "standard"}
    if task.name == "draft_reply":
        return {"text": f"Thank you for your message. Here is a first draft: {head[:80]}",
                "tone": "neutral", "signsOff": False}
    return {"text": head[:100]}


class MockProvider:
    name = "mock"

    async def complete(self, task: Task, model: str) -> str:
        rng = random.Random(f"overheard-mock:{task.name}:{model}:{task.system}\n{task.user}")
        t = _ctx(task)
        if t is None:
            out = _generic(task, rng, _script(task))
        else:
            out = {
                "summary": lambda: _summary(task, rng, t),
                "extraction": lambda: _extraction(task, rng, t),
                "intent_urgency": lambda: _intent(task, rng, t),
                "translation": lambda: _translation(task, rng, t, _script(task)),
                "sentiment": lambda: _sentiment(task, rng, t, _script(task)),
                "draft_reply": lambda: _draft(task, rng, t),
            }.get(task.name, lambda: _generic(task, rng, _script(task)))()
        return json.dumps(out, ensure_ascii=False)


def _check() -> None:  # pragma: no cover - manual check
    assert isinstance(MockProvider(), LLMProvider)


_check()
