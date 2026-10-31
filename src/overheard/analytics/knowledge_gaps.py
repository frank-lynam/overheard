"""View 8 of Mode 3: knowledge-gap mining.

Cross-references the archive's contacts against the centre's knowledge base
(`kb_articles`, whose `topics` list the call-drivers each article covers) and
ranks the questions callers ask often that no article answers. For each gap it
drafts a plain-code FAQ entry (title is a real caller phrasing, body is built
from the driver's measured data and the calendar events behind it) and a short
IVR line. It also flags weak coverage: drivers an article *claims* to cover
whose real phrasings use words the article never says (the planted fax-number
gap: 'Sending documents' says to mail them and never mentions a fax). No LLM.
"""

import json
import re
import sqlite3

from overheard.data.templates import DRIVERS

#: words too common to prove that an article fails to mention a topic
_STOP = {
    "i", "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "you", "your",
    "my", "me", "we", "us", "it", "is", "are", "was", "be", "will", "would", "can", "could",
    "may", "might", "should", "do", "does", "did", "what", "why", "how", "this", "that",
    "these", "those", "if", "as", "at", "by", "with", "from", "so", "not", "no",
    "has", "have", "had", "been", "being", "get", "got", "say", "says", "said", "tell",
    "when", "who", "whom", "which", "where", "all", "any", "each", "other", "another",
    "here", "there", "then", "than", "too", "very", "just", "only", "about", "after",
    "before", "again", "still", "never", "always", "ever", "own", "same", "them",
    "need", "needs", "please", "help", "want", "wants",
    "t", "c", "re", "ll", "ve", "d", "s", "don", "dont", "doesn", "didnt", "isnt",
    "werent", "arent", "haven", "hasnt", "yet", "month",
}


def _words(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _content_words(text: str) -> set[str]:
    return {t for t in _words(text) if t not in _STOP}


def _driver_info() -> dict[str, dict]:
    return {d[0]: {"team": d[1], "weekly": d[2], "handle": d[3], "resolve": d[4],
                   "phrasings": d[5]} for d in DRIVERS}


def _kb(con: sqlite3.Connection) -> list[dict]:
    out = []
    for r in con.execute("SELECT id, title, body, topics FROM kb_articles ORDER BY id"):
        out.append({"id": r["id"], "title": r["title"], "body": r["body"],
                    "topics": json.loads(r["topics"])})
    return out


def _driver_counts(con: sqlite3.Connection) -> dict[str, dict]:
    out = {}
    for r in con.execute(
        "SELECT root_cause, COUNT(*) n, COALESCE(SUM(handle_min), 0) h, "
        "COALESCE(SUM(resolved), 0) res FROM contacts GROUP BY root_cause"):
        out[r["root_cause"]] = {"count": r["n"], "hours": round(r["h"] / 60.0, 1),
                                "resolveRate": round(r["res"] / r["n"], 3)}
    return out


def _fill(template: str) -> str:
    """A phrasing like 'I got the 22-B letter, what do I need to re-verify?' already
    speaks in its own words; keep the most common plain forms as-is."""
    t = re.sub(r"\{doc\}", "the document", template)
    t = re.sub(r"\{month\}", "last month", t)
    t = re.sub(r"\{amount\}", "an amount", t)
    t = re.sub(r"\{language\}", "your language", t)
    return t


def _faq_body(driver: str, info: dict, count: int, resolve: float) -> str:
    """The plain-code answer an agent gives: the measured numbers, the likely
    reason (calendar events behind the driver), and what the archive's callers
    actually say, so the entry stays grounded in real language."""
    from overheard.data.events import EVENTS

    name = driver.replace("-", " ")
    body = (f"Callers ask about {name} {count:,} times over three years. "
            f"Those calls take about {info['handle']} minutes on average, "
            f"and {resolve:.0%} of them get resolved on the contact.")
    events = [e for e in EVENTS if e[5] == driver]
    if events:
        latest = max(events, key=lambda e: e[1])
        body += (f" A recent related event was '{latest[3]}' on {latest[1]}; "
                 f"recent events like that raise the volume, so expect a call about "
                 f"this question after one.")
    body += " Answer in the caller's words: " + _fill(info["phrasings"][0])
    return body


def _faq_title(driver: str, info: dict) -> str:
    """The FAQ title is a real caller phrasing, as the caller said it."""
    p = _fill(info["phrasings"][0]).strip()
    return p[0].upper() + p[1:] if p else driver.replace("-", " ")


def _ivr_line(driver: str, team: str) -> str:
    """A one-line IVR option for the new topic, in the centre's existing voice."""
    name = driver.replace("-", " ").strip()
    return (f"Say {name[0].upper()}{name[1:]} for help "
            f"with this topic from the {team} team")


def knowledge_gaps(con: sqlite3.Connection) -> dict:
    """The mode-3 view: ranked unanswered questions, weak coverage, and drafts."""
    kb = _kb(con)
    topics: dict[str, list[str]] = {}
    for a in kb:
        for t in a["topics"]:
            topics.setdefault(t, []).append(a["id"])
    counts = _driver_counts(con)
    info = _driver_info()

    covered_total = sum(c["count"] for d, c in counts.items() if d in topics)
    all_total = sum(c["count"] for c in counts.values())

    gaps = []
    for driver, c in counts.items():
        if driver in topics:
            continue
        i = info.get(driver)
        if i is None or c["count"] < 50:  # too rare to be worth an article
            continue
        gaps.append({
            "driver": driver,
            "name": driver.replace("-", " "),
            "count": c["count"],
            "hours": c["hours"],
            "resolveRate": c["resolveRate"],
            "sharePct": round(100.0 * c["count"] / all_total, 1),
            "faq": {"title": _faq_title(driver, i), "body": _faq_body(driver, i, c["count"], c["resolveRate"])},
            "ivr": _ivr_line(driver, i["team"]),
        })
    gaps.sort(key=lambda g: -g["count"])

    weak = []
    for a in kb:
        article_words = _content_words(a["title"] + " " + a["body"])
        missing: dict[str, list[str]] = {}
        for t in a["topics"]:
            i = info.get(t)
            if not i:
                continue
            for p in i["phrasings"]:
                pw = _content_words(p)
                for w in sorted(pw - article_words):
                    if re.fullmatch(r"(19|20)\d{2}", w):
                        continue
                    missing.setdefault(w, [])
                    if p not in missing[w]:
                        missing[w].append(p)
        gaps_found = {w: ps for w, ps in missing.items()}
        if gaps_found:
            weak.append({"articleId": a["id"], "articleTitle": a["title"],
                         "uncovered": gaps_found})

    return {
        "articles": len(kb),
        "coveredDrivers": len(topics),
        "drivers": len(info),
        "coveredContacts": covered_total,
        "allContacts": all_total,
        "coveragePct": round(100.0 * covered_total / all_total, 1) if all_total else 0.0,
        "gaps": gaps,
        "weakCoverage": weak,
    }
