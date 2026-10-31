"""View 6 of Mode 3: the letter lab — pre-test a draft notice against the archive.

Paste a draft letter and the tool (a) detects which archive call-driver it
sounds like, by word overlap with that driver's real phrasings and its events;
(b) predicts the call volume it will drive, from the measured excess of similar
past mailings (the same window-vs-baseline math as the event-impact view),
scaled by a readability/clarity score of the draft; (c) shows the questions
real archive readers actually asked about that notice; and (d) rewrites the
draft into a clearer letter and predicts the before/after. Plain code and SQL
over `contacts` + `events`; no LLM.
"""

import math
import re
import sqlite3
import statistics
from datetime import timedelta

from overheard.analytics.events import _baseline_rate, _weekdays, _window_counts
from overheard.data.events import EVENTS
from overheard.data.templates import DRIVERS

#: words too common to count as evidence in notice detection
_STOP = {
    "i", "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "you", "your",
    "my", "me", "we", "us", "it", "is", "are", "was", "be", "will", "would", "can", "could",
    "may", "might", "should", "do", "does", "did", "what", "why", "how", "this", "that",
    "these", "those", "if", "as", "at", "by", "with", "from", "so", "not", "no",
    "has", "have", "had", "been", "being", "get", "got", "say", "says", "said", "tell",
    "when", "who", "whom", "which", "where", "all", "any", "each", "other", "another",
    "here", "there", "then", "than", "too", "very", "just", "only", "about", "after",
    "before", "again", "still", "never", "always", "ever", "own", "same",
}

#: phrasings that read as bureaucratic, counted against the draft's clarity
_JARGON = ["re-verification", "determination", "prescribed", "pursuant", "documentation",
          "subject to", "thereafter", "aforementioned", "herein", "thereof"]

#: the jargon the rewrite swaps for plainer words, longest first
_SWAP = {
    "pursuant to our prescribed regulations": "by our rules",
    "pursuant to": "following",
    "the re-verification documentation": "the re-verification form",
    "re-verification documentation": "the re-verification form",
    "the documentation": "the form",
    "documentation": "the form",
    "made a determination that": "made the decision that",
    "require re-verification of your": "need you to re-verify your",
    "subject to further review": "while we check the details",
    "failure to": "if you do not",
    "fail to": "do not",
    "subject to": "and if we need",
    "determination": "decision",
    "prescribed": "standard",
    "re-verification": "re-verifying your details",
    "aforementioned": "the above",
    "in order to": "to",
    "thereafter": "after that",
    "herein": "in this letter",
    "thereof": "about it",
}

#: imperatives that count as "the letter tells the reader what to do"
_ACTION = ("send", "reply", "call", "submit", "visit", "upload", "bring", "do", "renew",
           "re-verify", "confirm", "respond", "answer", "return", "complete")


def _words(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _content(text: str) -> set[str]:
    return {t for t in _words(text) if t not in _STOP}


def _driver_info() -> dict[str, dict]:
    out = {}
    for d in DRIVERS:
        out[d[0]] = {"team": d[1], "weekly": d[2], "handle": d[3], "resolve": d[4],
                     "phrasings": d[5]}
    return out


def _driver_vocabulary(driver: str) -> set[str]:
    """The driver's real vocabulary: its phrasings plus its events' names/descriptions."""
    info = _driver_info()[driver]
    vocab = _content(" ".join(info["phrasings"]))
    for e in EVENTS:
        if e[5] == driver:
            vocab |= _content(f"{e[3]} {e[4]}")
    return vocab


def detect_notice(text: str) -> dict:
    """Which call-driver does this draft sound like? Word overlap with the driver's
    real phrasings and its events, scored against the size of that vocabulary."""
    draft = _content(text)
    rows = []
    for driver in _driver_info():
        vocab = _driver_vocabulary(driver)
        if not vocab:
            continue
        matched = sorted(draft & vocab)
        score = len(matched) / math.sqrt(len(vocab))
        rows.append({"driver": driver, "score": score, "overlap": len(matched), "matched": matched})
    rows.sort(key=lambda r: (-r["score"], -r["overlap"], r["driver"]))
    top = rows[0]
    mailings = [e[3] for e in EVENTS if e[5] == top["driver"] and e[2] == "mailing"]
    label = mailings[0].split("(")[0].strip() if mailings else top["driver"].replace("-", " ")
    return {"driver": top["driver"], "label": label, "score": round(top["score"], 3),
            "matchedWords": top["matched"], "runnerUp": rows[1]["driver"] if len(rows) > 1 else None}


def mailing_windows(con: sqlite3.Connection, driver: str) -> list[dict]:
    """Every mailing of this driver in the archive: window contacts vs. the driver's own
    baseline, and the excess (the same math as the event-impact view)."""
    out = []
    for e in EVENTS:
        eid, dstr, etype, name, _desc, drv, _peak, days = e
        if drv != driver or etype != "mailing":
            continue
        start = date_from(dstr)
        end = start + timedelta(days=days)
        count, _hours = _window_counts(con, driver, start, end)
        rate = _baseline_rate(con, driver, start)
        expected = rate * _weekdays(start, end)
        out.append({"event": eid, "date": dstr, "name": name, "count": count,
                    "expected": round(expected), "excess": round(max(0, count - expected))})
    out.sort(key=lambda w: w["date"])
    return out


def date_from(dstr: str):
    from datetime import date

    return date.fromisoformat(dstr)


def _avg_sentence_words(text: str) -> float:
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    lens = [len(_words(s)) for s in sents]
    return sum(lens) / len(lens) if lens else 0.0


def _deadline(text: str) -> str | None:
    m = re.search(r"within \d+ (?:business )?(?:calendar )?days", text, re.I)
    if m:
        return m.group(0)
    m = re.search(r"(?:by|no later than) (?:the )?\d{1,2}(?:st|nd|rd|th)? (?:of )?[a-z]+ [a-z]+", text, re.I)
    if m:
        return m.group(0)
    return None


def _has_action(text: str) -> bool:
    t = text.lower()
    return any(re.search(rf"\b{a}\b", t) for a in _ACTION)


def _plainness(text: str) -> float:
    hits = sum(1 for j in _JARGON if j in text.lower())
    words = max(1, len(_words(text)))
    return max(0.0, min(1.0, 1.0 - hits / (words / 40.0)))


def clarity_report(text: str) -> dict:
    """A readability score in [0, 1]: short sentences, an explicit deadline, an
    explicit action, and plain words. Fully deterministic."""
    avg = _avg_sentence_words(text)
    sent = max(0.0, min(1.0, 1.0 - (avg - 8.0) / 30.0))
    plain = _plainness(text)
    deadline = _deadline(text)
    action = _has_action(text)
    issues = []
    if avg > 20:
        issues.append(f"sents average {avg:.0f} words; split them")
    if not deadline:
        issues.append("no deadline in sight: what to do, and by when")
    if not action:
        issues.append("no clear action: what the reader must do")
    if plain < 0.5:
        issues.append("bureaucratic wording")
    score = 0.4 * sent + 0.25 * (1.0 if deadline else 0.0) + 0.2 * (1.0 if action else 0.0) + 0.15 * plain
    return {"score": round(score, 3), "avgSentenceWords": round(avg, 1),
            "hasDeadline": bool(deadline), "hasAction": action, "issues": issues}


def _split_long(sentences: list[str], limit: int = 20) -> list[str]:
    out = []
    for s in sentences:
        while len(_words(s)) > limit:
            cut = -1
            for m in re.finditer(r"\s+(?:and|but|which is|so|or)\s", s):
                cut = m.start()
            if cut <= 0 or cut >= len(s) - 2:
                break
            out.append(s[:cut].strip().rstrip(","))
            s = s[cut:].strip()
        out.append(s.strip())
    return [s for s in out if s]


def rewrite_letter(text: str) -> str:
    """The rule-based clearer-letter transform: swap jargon, split long sentences,
    title case, and pin an explicit 'What to do / When' block at the end."""
    t = " ".join(text.lower().split())
    _re = re.compile("|".join(re.escape(k) for k in sorted(_SWAP, key=len, reverse=True)))
    t = _re.sub(lambda m: _SWAP[m.group(0)], t)  # one pass: replaced text is not re-scanned
    t = re.sub(r"\bthe the\b", "the", t)
    t = " ".join(t.split())
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s.strip()]
    body = _split_long(sents)
    body = [s[0].upper() + s[1:] if s and not s[0].isupper() else s for s in body]
    body = [s if s[-1] in ".!?" else s + "." for s in body]
    when = _deadline(t) or "no later than the date printed on this letter"
    block = [
        "What to do:",
        "1. Send the information we asked for, to the address on this letter.",
        "2. If you need help, call the number on this letter; asking questions will not count against you.",
        f"When: {when}.",
    ]
    return " ".join(body) + "\n" + "\n".join(block)


def letter_lab(con: sqlite3.Connection, text: str) -> dict:
    """The full letter-lab result for a draft notice."""
    det = detect_notice(text)
    driver = det["driver"]
    resolve = _driver_info()[driver]["resolve"]
    windows = mailing_windows(con, driver)
    excesses = [w["excess"] for w in windows]

    def predict(clarity_score: float) -> tuple[float, float, float]:
        scale = 1.0 + 0.6 * (0.5 - clarity_score)  # vague letters cost more, clear letters less
        if excesses:
            low, mid, high = min(excesses) * scale, statistics.median(excesses) * scale, max(excesses) * scale
            return low, mid, high
        # no similar mailings: the driver's measured business-as-usual week, scaled the same way
        end = date_from(con.execute("SELECT MAX(at) FROM contacts").fetchone()[0][:10])
        day, count = end - timedelta(days=1), 0
        while count < 90:
            if day.weekday() < 5:
                count += 1
            day -= timedelta(days=1)
        total, _h = _window_counts(con, driver, day, end)
        mid = total / max(1, count) * 5 * scale
        return mid * 0.8, mid, mid * 1.25

    clarity = clarity_report(text)
    low, mid, high = predict(clarity["score"])
    confusion = max(0.03, min(0.95, (1.0 - resolve) * (1.25 - clarity["score"])))
    questions_before = round(mid * confusion)

    rewritten = rewrite_letter(text)
    clarity2 = clarity_report(rewritten)
    low2, mid2, high2 = predict(clarity2["score"])
    confusion2 = max(0.03, min(0.95, (1.0 - resolve) * (1.25 - clarity2["score"])))
    questions_after = round(mid2 * confusion2)

    samples = con.execute(
        "SELECT text, channel, at FROM contacts WHERE root_cause = ? ORDER BY at LIMIT 6", (driver,)).fetchall()
    total_q = con.execute("SELECT COUNT(*) FROM contacts WHERE root_cause = ?", (driver,)).fetchone()[0]

    return {
        "detected": det,
        "predicted": {"low": round(low), "mid": round(mid), "high": round(high),
                      "method": "similar past mailings" if excesses else "driver baseline",
                      "perMailing": windows},
        "archiveQuestions": {"count": total_q,
                             "sample": [{"text": r["text"], "channel": r["channel"], "at": r["at"]}
                                        for r in samples]},
        "clarity": clarity,
        "rewrite": {
            "text": rewritten,
            "clarityScore": clarity2["score"],
            "avgSentenceWords": clarity2["avgSentenceWords"],
            "predicted": {"low": round(low2), "mid": round(mid2), "high": round(high2)},
            "questionsBefore": questions_before,
            "questionsAfter": questions_after,
            "volumeBefore": round(mid),
            "volumeAfter": round(mid2),
            "reductionPct": round(1.0 - mid2 / mid, 3) if mid else 0.0,
        },
    }
