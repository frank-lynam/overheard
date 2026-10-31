"""View 7 of Mode 3: ask the archive.

Plain-English questions ("Why did calls about the 22-B letter spike in June 2025?") are
answered by plain code over pre-computed totals of the archive's `contacts` table:
how many, what share of that issue's traffic, how the period compares to the equal
period before it, which calendar events (mailings, releases, policy changes) overlap
the period, and a few real messages from the archive cited as evidence. A question
the parser can't scope gets an honest "I don't know" instead of a guess. No LLM.
"""

import re
import sqlite3
from datetime import date, timedelta

from overheard.data.events import EVENTS
from overheard.data.generator import END, START
from overheard.data.templates import DRIVERS, MONTHS

#: words too common to count as evidence when matching a cause
_STOP = {
    "i", "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "you", "your",
    "my", "me", "we", "us", "it", "is", "are", "was", "be", "will", "would", "can", "could",
    "may", "might", "should", "do", "does", "did", "what", "why", "how", "this", "that",
    "these", "those", "if", "as", "at", "by", "with", "from", "so", "not", "no",
    "has", "have", "had", "been", "being", "get", "got", "say", "says", "said", "tell",
    "when", "who", "whom", "which", "where", "all", "any", "each", "other", "another",
    "here", "there", "then", "than", "too", "very", "just", "only", "about", "after",
    "before", "again", "still", "never", "always", "ever", "own", "same",
    "double", "doubled", "spike", "spiked", "surge", "surged", "increase", "increased",
    "drop", "dropped", "because", "people", "call", "calls", "calling", "contact",
    "contacts", "many", "much", "last", "previous", "period", "issue", "issues",
    "problem", "problems", "lot", "lots", "more", "less", "up", "down", "across",
    "language", "languages",
}

_MONTH_NUM = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
_REGIONS = [
    ("oh", "Ohio"), ("ca", "California"), ("tx", "Texas"), ("fl", "Florida"), ("ny", "New York"),
    ("pa", "Pennsylvania"), ("il", "Illinois"), ("ga", "Georgia"), ("nc", "North Carolina"),
    ("mi", "Michigan"), ("az", "Arizona"), ("wa", "Washington"), ("tn", "Tennessee"),
    ("ky", "Kentucky"), ("md", "Maryland"), ("nm", "New Mexico"), ("nv", "Nevada"),
    ("or", "Oregon"), ("mn", "Minnesota"), ("me", "Maine"),
]
_LANGS = [
    (["spanish"], "es", "Spanish"), (["vietnamese"], "vi", "Vietnamese"),
    (["tagalog"], "tl", "Tagalog"), (["chinese"], "zh", "Chinese"),
    (["english"], "en", "English"),
]
_CUTOFF = 15  # a month-count below this is noise, not a spike or a crash


def _words(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _stem(t: str) -> str:
    """'22-b' and '22B' both mean the 22-B form: compare digits + letters only."""
    return re.sub(r"[^a-z0-9]", "", t)


def _driver_info() -> dict[str, dict]:
    out = {}
    for d in DRIVERS:
        out[d[0]] = {"team": d[1], "weekly": d[2], "handle": d[3], "resolve": d[4],
                     "phrasings": d[5]}
    return out


def _driver_vocabulary(driver: str) -> set[str]:
    """The driver's real vocabulary: its phrasings plus its events' names/descriptions."""
    info = _driver_info()[driver]
    vocab = {t for t in _words(" ".join(info["phrasings"])) if t not in _STOP}
    for e in EVENTS:
        if e[5] == driver:
            vocab |= {t for t in _words(f"{e[3]} {e[4]}") if t not in _STOP}
    return vocab


def _parse_cause(question: str) -> tuple[str, list[str]] | None:
    """Which call-driver is the question about? Best word overlap with the driver's
    real phrasings and events; a few content words must actually match."""
    draft = {t for t in _words(question) if t not in _STOP}
    lang_stems = {_stem(w) for words, _c, _n in _LANGS for w in words}
    year_words = {t for t in draft if re.fullmatch(r"(19|20)\d{2}", t)}
    probes = {_stem(t) for t in draft
              if t not in year_words and _stem(t) not in lang_stems}
    aliases = {
        # what real people say about an issue, in words the issue's phrasings don't use
        "signin": {"password", "login", "portal"},
        "password": {"login"},
        "portal": {"portal"},
        "portals": {"portal"},
        "failure": {"error"},
        "failures": {"error"},
        "problems": {"error"},
    }
    for a in probes & set(aliases):
        probes |= aliases[a]
    best, best_overlap, second = None, 0, 0
    rarity: dict[str, int] = {}
    for driver in _driver_info():
        vocab = {_stem(t) for t in _driver_vocabulary(driver)}
        n = len(probes & vocab)
        if n > best_overlap:
            second, best, best_overlap = best_overlap, driver, n
        elif n > second:
            second = n
        for t in probes & vocab:
            rarity[t] = rarity.get(t, 0) + 1
    # a single word that only one driver ever uses ("1099", "22-b") is a strong match
    lone = {t for t in probes
            if rarity.get(t) == 1 and not re.fullmatch(r"(19|20)\d{2}", t)}
    if best is not None and best_overlap >= 2 and second <= 1:
        return best, sorted(t for t in draft if _stem(t) in {t for t in _driver_vocabulary(best)})
    if best is None or best_overlap < 3:
        for t in sorted(lone):
            owners = {d for d in _driver_info()
                      if any(_stem(s) == _stem(t) for s in _driver_vocabulary(d))}
            if len(owners) == 1 and not (best and best_overlap > 1):
                return next(iter(owners)), [t]
        return None
    vocab = {_stem(t) for t in _driver_vocabulary(best)}
    return best, sorted(t for t in draft if _stem(t) in vocab)


def _parse_period(question: str) -> tuple[date, date, str] | None:
    """The month(s) the question is about, from "June 2025" / "last June" / "June" / "in 2025".

    "Last <month>" means the most recent occurrence before the archive ends."""
    q = question.lower()
    year = None
    m = re.search(r"\b(19|20)\d{2}\b", q)
    if m:
        year = int(m.group(0))
    month = None
    for name in MONTHS:
        if re.search(rf"\b{re.escape(name.lower())}\b", q):
            month = _MONTH_NUM[name.lower()]
            break
    if month:
        if re.search(rf"\blast\s+{re.escape(MONTHS[month - 1].lower())}\b", q):
            year = (END - timedelta(days=1)).year
        if year is None:
            year = (END - timedelta(days=1)).year
        start = date(year, month, 1)
        nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start, min(nxt, END), f"{MONTHS[month - 1]} {year}"
    if year and START.year <= year <= END.year:
        return date(year, 1, 1), min(date(year + 1, 1, 1), END), str(year)
    return None


def _scope_totals(con: sqlite3.Connection, *, driver: str | None = None,
                  region: str | None = None, lang: str | None = None,
                  start: date, end: date) -> tuple[int, float]:
    sql = "SELECT COUNT(*), COALESCE(SUM(handle_min), 0) FROM contacts WHERE at >= ? AND at < ?"
    args: list = [start.isoformat(), end.isoformat()]
    if driver:
        sql += " AND root_cause = ?"
        args.append(driver)
    if region:
        sql += " AND region = ?"
        args.append(region.upper())
    if lang:
        sql += " AND lang = ?"
        args.append(lang)
    row = con.execute(sql, args).fetchone()
    return row[0], row[1] / 60.0


def _prior_period(start: date, end: date) -> tuple[date, date]:
    span = (end - start).days
    p_end = start - timedelta(days=1)
    p_start = p_end - timedelta(days=span - 1)
    return p_start, p_end


def _evidence(con: sqlite3.Connection, *, driver: str | None = None,
              region: str | None = None, lang: str | None = None,
              start: date, end: date, limit: int = 4) -> list[str]:
    sql = "SELECT text FROM contacts WHERE at >= ? AND at < ?"
    args: list = [start.isoformat(), end.isoformat()]
    if driver:
        sql += " AND root_cause = ?"
        args.append(driver)
    if region:
        sql += " AND region = ?"
        args.append(region.upper())
    if lang:
        sql += " AND lang = ?"
        args.append(lang)
    sql += " ORDER BY RANDOM() LIMIT ?"
    args.append(limit)
    seen, out = set(), []
    for (text,) in con.execute(sql, args):
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _coincident_events(driver: str | None, start: date, end: date) -> list[dict]:
    """Calendar events whose window overlaps the question's period, and (for cause
    questions) events about the same cause first: the likely reason for a spike."""
    out = []
    for e in EVENTS:
        eid, dstr, etype, name, _desc, drv, _peak, days = e
        ev_start = date.fromisoformat(dstr)
        ev_end = ev_start + timedelta(days=days)
        if ev_start < end and ev_end > start:
            out.append({"id": eid, "date": dstr, "type": etype, "name": name,
                        "driver": drv, "sameCause": drv == driver if driver else None,
                        "window": f"{dstr} to {ev_end.isoformat()}"})
    out.sort(key=lambda x: (not x["sameCause"], x["date"]))
    return out


def _answer(con: sqlite3.Connection, driver: str | None, label: str | None,
            region: str | None, lang: str | None, period: tuple[date, date, str] | None) -> dict:
    """Fill the answer with totals: counts for the scope, its share of that issue's
    traffic, change versus the equal period before, coincident events, real examples."""
    answer: dict = {"driver": driver, "region": region, "lang": lang,
                    "period": period[2] if period else None,
                    "count": None, "priorCount": None, "change": None, "changePct": None,
                    "causeCount": None, "causeShare": None, "events": [], "evidence": []}
    start, end = (period[0], period[1]) if period else (START, END)

    if period:
        count, _hours = _scope_totals(con, driver=driver, region=region, lang=lang,
                                      start=start, end=end)
        answer["count"] = count
        p_start, p_end = _prior_period(start, end)
        prior, _ = _scope_totals(con, driver=driver, region=region, lang=lang,
                                 start=p_start, end=p_end)
        answer["priorCount"] = prior
        if prior:
            answer["change"] = count - prior
            answer["changePct"] = round(100.0 * (count - prior) / prior)
        if count >= _CUTOFF or prior >= _CUTOFF:
            answer["events"] = _coincident_events(driver, start, end)

    if driver:
        cause_count, _ = _scope_totals(con, driver=driver, start=START, end=END)
        answer["causeCount"] = cause_count
        if period and count is not None and cause_count:
            answer["causeShare"] = round(100.0 * count / cause_count, 1)

    answer["evidence"] = _evidence(con, driver=driver, region=region, lang=lang,
                                   start=start, end=end)
    return answer


def _render(answer: dict, driver_label: str, region_label: str | None,
            lang_label: str | None) -> str:
    """Turn the totals into a plain-English answer with an honest structure."""
    scope_bits = []
    if driver_label:
        scope_bits.append(driver_label)
    if region_label:
        scope_bits.append(region_label)
    if lang_label:
        scope_bits.append(lang_label)
    scope = " ".join(scope_bits) if scope_bits else "all of the archive's contacts"
    period = answer["period"] or "the whole archive"

    if answer["count"] is not None:
        head = f"{answer['count']:,} contacts in {scope}, {period}."
        if answer["priorCount"] is not None and (answer["count"] >= _CUTOFF
                                                 or answer["priorCount"] >= _CUTOFF):
            if answer["changePct"] is not None:
                pct = answer["changePct"]
                if pct >= 100:
                    trend = f"up about {pct / 100.0:.1f}x versus the equal period before"
                elif pct >= 20:
                    trend = f"up {pct}% versus the equal period before"
                elif pct <= -20:
                    trend = f"down {abs(pct)}% versus the equal period before"
                else:
                    trend = "about the same as the equal period before"
                head += (f" That's {trend} "
                          f"({answer['priorCount']:,} before).")
            if answer["causeShare"] is not None:
                head += (f" {answer['causeShare']}% of this issue's archive traffic "
                         f"({answer['causeCount']:,} in total) falls in this period.")
    else:
        head = f"All of {scope} over {period}:"

    if answer["count"] == 0:
        head = f"No contacts in {scope} for {period}."
    return head


def ask(con: sqlite3.Connection, question: str) -> dict:
    """Answer a plain-English question over the archive's pre-computed totals."""
    q = question.strip()
    if not q:
        return {"question": q, "understood": False,
                "answer": "Ask me about an issue, a place, a language, and a month — "
                          f"the archive runs {START.isoformat()} to {END.isoformat()}."}

    parsed = _parse_cause(q)
    driver, matched = parsed if parsed else (None, [])
    period = _parse_period(q)
    region = next((code for code, name in _REGIONS if re.search(rf"\b{re.escape(name.lower())}\b",
                                                                q.lower())), None)
    lang = next((code for words, code, _name in _LANGS
                 if any(re.search(rf"\b{re.escape(w)}\b", q.lower()) for w in words)), None)
    region_label = dict((code, name) for code, name in _REGIONS).get(region)
    lang_label = dict((code, name) for _w, code, name in _LANGS).get(lang)

    if driver is None and region is None and lang is None and period is None:
        return {"question": q, "understood": False,
                "answer": f"I can count contacts by issue, state, language and month "
                          f"({START.isoformat()} to {END.isoformat()}), but I couldn't tell "
                          f"what you're asking about. Try: 'Why did portal sign-in failures "
                          f"spike in May 2025?' or 'How many 22-B letter contacts were there in "
                          f"June 2025 in Ohio?'"}

    label = None
    if driver:
        mailings = [e[3] for e in EVENTS if e[5] == driver and e[2] == "mailing"]
        label = mailings[0].split("(")[0].strip() if mailings else driver.replace("-", " ")
    answer = _answer(con, driver, label, region, lang, period)
    text = _render(answer, label, region_label, lang_label)

    if answer["events"] and (answer["changePct"] is not None and answer["changePct"] >= 20):
        ev = answer["events"][0]
        reason = (f"The most likely reason: {ev['name']} "
                  f"({ev['type']}, {ev['window']}) — its window overlaps this period."
                  + ("" if ev.get("sameCause") else ""))
        text += " " + reason
    elif answer["events"]:
        names = "; ".join(e["name"] for e in answer["events"][:3])
        text += f" Calendar events overlapping this period: {names}."

    if answer["evidence"] and answer["count"]:
        examples = " | ".join(answer["evidence"][:4])
        text += f" Real messages from the archive in this period: {examples}"

    return {"question": q, "understood": True, "answer": text, "matchedCause": driver,
            "matchedWords": matched, "region": region, "lang": lang, "totals": answer}
