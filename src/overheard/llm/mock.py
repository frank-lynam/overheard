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
DIGITS = {"oh": "0", "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
          "six": "6", "seven": "7", "eight": "8", "nine": "9"}


def _digit_runs(script: str) -> list[tuple[int, int, str]]:
    """Runs of spoken digits ("oh one oh six") in the transcript: (start, end, digits)."""
    runs = []
    start, last_end, buf = None, None, ""
    for m in re.finditer(r"[A-Za-z']+", script):
        if m.group().lower() in DIGITS:
            if start is None:
                start = m.start()
                buf = ""
            buf += DIGITS[m.group().lower()]
            last_end = m.end()
        elif start is not None:
            if len(buf) >= 4:
                runs.append((start, last_end, buf))
            start, last_end, buf = None, None, ""
    if start is not None and len(buf) >= 4:
        runs.append((start, last_end, buf))
    return runs


def _find(run_digits: str, in_runs: list[tuple[int, int, str]]) -> tuple[int, int] | None:
    for start, end, digits in in_runs:
        if digits == run_digits or digits[-len(run_digits):] == run_digits:
            return start, end
    return None


def _field(value: str | None, conf: float, span: list[int] | None = None) -> dict:
    return {"value": value, "confidence": conf, "span": span}


def _ctx(task: Task) -> dict[str, Any] | None:
    if not task.context:
        return None
    try:
        return json.loads(task.context)
    except json.JSONDecodeError:
        return None


def _script(task: Task) -> str:
    # the transcript is the middle of the user prompt: after the first newline, before the "\n\n" ask
    user = task.user
    start = user.find("\n") + 1
    end = user.find("\n\n", start)
    return user[start:end if end != -1 else len(user)]


def _wrong(rng: random.Random) -> bool:
    return rng.random() > ACCURACY


def _summary(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    gist = t.get("englishGist") or (t.get("intent") or "a call about an account").replace("_", " ") + " call"
    text = gist if gist.endswith(".") else gist + "."
    if t.get("callerName"):
        text = f"{t['callerName']}: {text}"
    short = " ".join(text.split()[:8])  # headline: who + what
    if _wrong(rng):
        return {"short": short[: max(12, len(short) // 2)].rstrip(), "summary": text[: max(30, len(text) // 2)].rstrip()}
    return {"short": short, "summary": text}


def _extraction(task: Task, rng: random.Random, t: dict[str, Any], script: str) -> dict:
    runs = _digit_runs(script)
    conf = lambda: round(0.85 + rng.random() * 0.14, 2)  # noqa: E731 - seeded, per field
    caller = t.get("callerName")
    caller_span = None
    if caller:
        for word in reversed(caller.split()):  # the last word is the least common
            m = re.search(rf"\b{re.escape(word)}\b", script, re.I)
            if m:
                caller_span = [m.start(), m.end()]
                break
    case_id = t.get("caseId")
    case_span = None
    case_conf = 0.4
    if case_id:
        digits = re.sub(r"\D", "", case_id)[-6:]
        hit = _find(digits, runs)
        if hit:
            m = re.search(r"\b\d{3}-\d{4}\b", script)  # the digit style, not spoken
            case_span, case_conf = list(hit), conf()
        elif re.search(r"FBS", script, re.I):
            m = re.search(r"FBS", script, re.I)
            case_span, case_conf = [m.start(), m.start() + 6], 0.6  # heard it, but garbled
    callback = t.get("callbackNumber")
    cb_span = None
    cb_conf = 0.4
    if callback:
        digits = re.sub(r"\D", "", callback)[-10:]
        hit = _find(digits, runs)
        if hit:
            cb_span, cb_conf = list(hit), conf()
        elif re.search(r"\d{3}-\d{4}", script):
            m = re.search(r"\d{3}-\d{4}", script)
            cb_span, cb_conf = [m.start(), m.end()], 0.5
    program = None
    prog_conf = 0.4
    if t.get("intent") == "portal_access":
        program, prog_conf = "benefit account portal", 0.5  # inferred, not stated
    elif t.get("intent") in ("other", "compliment", "wrong-agency"):
        program = None
    else:
        program, prog_conf = "federal cash benefit payments", 0.5  # inferred from the topic
    action_cb = re.search(r"call (me|you) back|give me a call|call me|reach me|contact me|contact you", script, re.I)
    action_wr = re.search(r"\bemail(e)? me\b|\bwrite (me|back)\b", script, re.I)
    if action_cb:
        action_value, action_conf, action_span = "call back", 0.6, [action_cb.start(), action_cb.end()]
    elif action_wr:
        action_value, action_conf, action_span = "written reply", 0.6, [action_wr.start(), action_wr.end()]
    else:
        # a letter merely *got* ("I got a letter") isn't an ask to write; a call back is the default
        action_value, action_conf, action_span = "call back", 0.5, None  # assumed
    out = {
        "caller": _field(caller, conf() if caller_span else 0.7, caller_span),
        "callbackNumber": _field(callback, cb_conf, cb_span),
        "caseId": _field(case_id, case_conf, case_span),
        "program": _field(program, prog_conf, None),
        "requestedAction": _field(action_value, action_conf, action_span),
        "caseNumberSaid": bool(t.get("caseNumberSaid", True)),
    }
    if _wrong(rng):
        if out["caseId"]["value"] is not None:
            out["caseId"] = _field(None, 0.3, None)  # heard it, wrote it down wrong, dropped it
        elif out["caller"]["value"]:
            out["caller"] = _field(out["caller"]["value"].split()[0], 0.8, caller_span)  # first name only
        elif out["callbackNumber"]["value"]:
            v = out["callbackNumber"]["value"]
            out["callbackNumber"] = _field(v[:-1] + "0", cb_conf, cb_span)  # last digit off
    return out


def _intent(task: Task, rng: random.Random, t: dict[str, Any], script: str) -> dict:
    out = {"intent": t.get("intent", "other"), "urgency": int(t.get("urgency", 2))}
    if out["urgency"] >= 5:
        reason = "There is a same-day deadline in the message; without action, the caller's day is at risk."
    elif out["urgency"] >= 3:
        reason = "The caller is pressing for a same-day answer because something is due soon."
    else:
        reason = "A status question that can wait for the usual queue."
    out["rationale"] = f"{t.get('intent', 'other').replace('_', ' ').title()}: {reason}"
    out["obligations"] = list(t.get("obligations") or [])  # the mock reads the flag straight from the truth
    if _wrong(rng) and out["urgency"] < 5:  # the mock is calibrated on urgency-5: those always get through
        if rng.random() < 0.5:
            out["intent"] = WRONG_INTENT
        else:
            out["urgency"] = max(1, min(5, out["urgency"] + (1 if rng.random() < 0.5 else -1)))
    return out


def _routing(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    t = t or {}
    intent = t.get("intent")
    urgency = int(t.get("urgency", 2))
    if urgency >= 5 or intent in ("urgent_hardship", "welfare"):
        team, reason = "escalations", "Urgency is 5: the caller's day is at risk, so the escalations team works it today."
    elif intent == "portal_access":
        team, reason = "portal_support", "A portal sign-in problem goes to the portal team."
    elif intent in ("status_payment", "direct_deposit_change", "overpayment"):
        team, reason = "payments", "A payment problem is the payments team's queue."
    elif intent in ("status_document", "form_question"):
        team, reason = "accounts", "Paperwork questions are worked by the accounts team."
    elif intent in ("congressional", "records_request", "complaint"):
        team, reason = "correspondence", "Offices, records and complaints go to correspondence."
    elif intent in ("address_change",):
        team, reason = "accounts", "Case-record changes go to accounts."
    else:
        team, reason = "general", "Nothing points at a specialist queue, so it goes to general."
    if _wrong(rng) and team != "escalations":
        team, reason = "general", "A call that looks routine was sent to the general queue."
    return {"team": team, "reason": reason}


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


def _resolution(task: Task, rng: random.Random, t: dict[str, Any]) -> dict:
    """The from-truth answer: resolvable when the truth says the lookups settle it,
    a reply grounded in the case record the task carries, and the belief mismatch
    verbatim. The same seeded-mistake rate as everything else: sometimes the mock
    says a solvable one needs a call, or vice versa."""
    resolvable = bool(t.get("resolvableBy"))
    case = t.get("caseId") or "your case"
    name = (t.get("callerName") or "there").split()
    first = name[0] if name else "there"
    if resolvable:
        lookups = []
        if t.get("intent") in ("status_payment",):
            lookups.append("payment_schedule")
        elif t.get("intent") in ("status_document", "form_question"):
            lookups.append("documents_received")
        lookups.append("case_status")
        reply = (f"Hi {first}, this is the Federal Benefits Service Center. Good news on {case}: "
                 "we checked your record and your question is answered — "
                 "no action is needed on your side unless we hear otherwise.")
        if t.get("beliefMismatch"):
            reply += " (Where the record and your letter disagree, the record wins; we'll note it on your file.)"
        answer = "The case record answers the question directly."
        brief = "Resolved by lookups; call only if the caller calls back."
        if _wrong(rng):
            resolvable = False  # the mock second-guesses itself and asks for a call
    else:
        lookups = ["case_status"]
        answer = "The record narrows it down, but a person has to make the call."
        reply = ""
        brief = (f"Case {case}. Prior contacts: {', '.join(t.get('linkedTo') or []) or 'none today'}. "
                 "Likely answer: see the case record's last action; confirm before promising a date.")
    out = {
        "resolvable": resolvable,
        "lookups": lookups,
        "answer": answer,
        "reply": reply,
        "brief": brief,
        "beliefMismatch": t.get("beliefMismatch"),
    }
    return out


def _generic(task: Task, rng: random.Random, script: str) -> dict:
    """No context (a hand-built task): a deterministic plausible answer from the text alone."""
    head = script[:180].strip()
    if task.name == "summary":
        return {"short": " ".join(head.split()[:8]), "summary": head + ("..." if len(script) > len(head) else "")}
    if task.name == "extraction":
        case = re.search(r"F B S[\s ]*([0-9]{4,7})", script, re.I)
        return {"caller": {"value": None, "confidence": 0.3, "span": None},
                "callbackNumber": {"value": None, "confidence": 0.3, "span": None},
                "caseId": {"value": f"FBS-{case.group(1)}" if case else None,
                           "confidence": 0.8 if case else 0.3, "span": list(case.span()) if case else None},
                "program": {"value": None, "confidence": 0.3, "span": None},
                "requestedAction": {"value": "call back", "confidence": 0.4, "span": None},
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
        return {"intent": intent, "urgency": 3 if re.search(r"urgent|asap|right away", script, re.I) else 2,
                "rationale": "Guessed from a few words in the transcript.", "obligations": []}
    if task.name == "routing":
        return {"team": "general", "reason": "No strong signal, so it goes to the general queue."}
    if task.name == "translation":
        return {"translated": False, "text": head, "sourceLang": "en"}
    if task.name == "sentiment":
        return {"sentiment": "calm", "escalation": "standard"}
    if task.name == "draft_reply":
        return {"text": f"Thank you for your message. Here is a first draft: {head[:80]}",
                "tone": "neutral", "signsOff": False}
    if task.name == "resolution":
        return {"resolvable": bool(re.search(r"F B S[\s ]*[0-9]{4,7}", script, re.I)),
                "lookups": ["case_status"],
                "answer": "The case record may answer it; verify before replying.",
                "reply": "", "brief": "No context was available; work the case record by hand.",
                "beliefMismatch": None}
    if task.name == "incident":  # a spike cluster: name it from the words the callers actually used
        code = re.search(r"error\s*(\d{3,})", script, re.I)
        if re.search(r"portal|sign(ing)? in|password", script, re.I):
            what = "Portal sign-in failure" + (f" (error {code.group(1)})" if code else "")
            cause = "A portal change is breaking sign-in; callers are phoning instead of retrying."
            banner = "The portal sign-in is down. We are aware of it; no need to call again."
        elif code:
            what = f"System failure (error {code.group(1)})"
            cause = "The callers describe the same failing screen; the most likely cause is that page's service."
            banner = "We are aware of the issue you're calling about and it is being fixed."
        else:
            what = "A burst of similar messages"
            cause = "The callers describe the same problem in their own words; the cause is still being pinned down."
            banner = "We are aware of the issue you're calling about and it is being fixed."
        return {"title": what, "probableCause": cause, "banner": banner,
                "actions": ["Show the banner to new callers immediately",
                            "Open a P1 ticket for the responsible team",
                            "Send the holding reply to every caller in the cluster"]}
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
                "extraction": lambda: _extraction(task, rng, t, _script(task)),
                "intent_urgency": lambda: _intent(task, rng, t, _script(task)),
                "routing": lambda: _routing(task, rng, t),
                "translation": lambda: _translation(task, rng, t, _script(task)),
                "sentiment": lambda: _sentiment(task, rng, t, _script(task)),
                "draft_reply": lambda: _draft(task, rng, t),
                "resolution": lambda: _resolution(task, rng, t),
            }.get(task.name, lambda: _generic(task, rng, _script(task)))()
        return json.dumps(out, ensure_ascii=False)


def _check() -> None:  # pragma: no cover - manual check
    assert isinstance(MockProvider(), LLMProvider)


_check()
