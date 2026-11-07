"""`overheard seed`: the hand-written day (seed_today.json) plus a three-year archive generated from a fixed seed.
Same seed, same data. The archive's planted signals are in events.py and in the knobs below."""

import json
import math
import random
from datetime import date, timedelta
from importlib.resources import files
from pathlib import Path

from overheard.data import db
from overheard.data.events import EVENTS
from overheard.data.templates import DOCS, DRIVERS, LANGUAGES, MONTHS

START, END = date(2023, 3, 10), date(2026, 3, 9)         # the archive: three years up to the day before "today"
LANGS = [("en", 0.80), ("es", 0.13), ("vi", 0.03), ("tl", 0.02), ("zh", 0.02)]
REGIONS = [("CA", 12), ("TX", 10), ("FL", 8), ("NY", 7), ("PA", 5), ("OH", 5), ("IL", 5), ("GA", 4), ("NC", 4), ("MI", 4),
           ("AZ", 3), ("WA", 3), ("TN", 3), ("KY", 2), ("MD", 2), ("NM", 2), ("NV", 2), ("OR", 2), ("MN", 2), ("ME", 1)]
VOLUME = 6.75               # scales every driver and event alike: ~90 contacts a weekday (~27 of them voicemail),
                            # so the 60-voicemail "today" is a normal day plus an incident: about 70,000 contacts
CALLERS = 25000             # the archive's caller pool (cases)
LOOP_SHARE = 0.04            # PLANTED: callers stuck in a loop: 3-6 contacts on one issue, never resolved
SLOW_LANG = "vi"             # PLANTED: slower, less often resolved service for one language
BROKEN = {"appeal-status": 0.62, "claim-status": 0.35, "identity-check-hold": 0.45}   # PLANTED: promises broken
FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", "Maria",
         "Jose", "Thi", "Van", "Nguyen", "Rosa", "Carlos", "Wei", "Mei", "Ana", "Luis", "Grace", "Samuel", "Ruth"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Nguyen", "Tran", "Le", "Santos", "Reyes", "Cruz", "Chen", "Wang", "Kim", "Patel", "Okafor", "Kowalski"]
KB = [
    ("kb-payment-dates", "When payments arrive", "Payments arrive on the 3rd; from March 2026, on the 12th.", ["payment-status", "payment-date-shift"]),
    ("kb-direct-deposit", "Changing your bank account", "Send Form 14; changes take effect within 10 business days.", ["direct-deposit-change", "returned-deposit"]),
    ("kb-address", "Changing your address", "Send Form 9 or update it in the portal; processed in 5 business days.", ["address-change", "temporary-address"]),
    ("kb-portal-signin", "Signing in to the portal", "Use the code sent by text; codes expire after 10 minutes.", ["portal-sign-in-failure", "password-reset"]),
    ("kb-documents", "Sending documents", "Mail documents to the address on your letter.", ["document-submission-method", "document-received-confirmation"]),
    ("kb-cola", "Cost-of-living adjustments", "Amounts change each January; your letter shows the new amount.", ["cola-letter"]),
    ("kb-overpayment", "Overpayment notices", "You can ask for a waiver or a repayment plan within 30 days.", ["overpayment-notice"]),
    ("kb-appeals", "Appeals", "Appeals are decided in order received.", ["appeal-status"]),
    # PLANTED gaps: no article explains Form 22-B re-verification, a fax number, or the 1099 vendor change.
]


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:                                       # normal approximation for big days
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    k, p, target = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= target:
            return k
        k += 1


def pick(rng: random.Random, weighted) -> str:
    total = sum(w for _, w in weighted)
    r, acc = rng.random() * total, 0.0
    for value, w in weighted:
        acc += w
        if r <= acc:
            return value
    return weighted[-1][0]


def say(rng: random.Random, phrasings: list[str]) -> str:
    text = rng.choice(phrasings)
    return text.format(month=rng.choice(MONTHS), amount=f"${rng.randint(4, 120) * 10}",
                       doc=rng.choice(DOCS), language=rng.choice(list(LANGUAGES.values())))


def seed(path: Path | str, seed_value: int = 2026) -> dict:
    """Write the day and the archive to a fresh database at `path`. Returns counts."""
    rng = random.Random(seed_value)
    con = db.create(path)
    today = json.loads((files("overheard.data") / "seed_today.json").read_text(encoding="utf-8"))
    for v in today["voicemails"]:
        con.execute("INSERT INTO voicemails VALUES (?,?,?,?,?,?,?)",
                    (v["id"], v["receivedAt"], v["callerId"], v["durationSec"], v["lang"], v["script"], db.j(v["truth"])))
    for c in today["cases"]:
        con.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (c["id"], c["name"], c["phone"], c["status"], c["region"], c["lang"], db.j(c["payments"]),
                     db.j(c["docs"]), c["lastAction"], c["team"]))
    for e in EVENTS:
        con.execute("INSERT INTO events VALUES (?,?,?,?,?)", e[:5])
    for k in KB:
        con.execute("INSERT INTO kb_articles VALUES (?,?,?,?)", (k[0], k[1], k[2], db.j(k[3])))

    # The archive's callers: a pool of cases, each with a language and region
    callers = []
    for i in range(CALLERS):
        lang, region = pick(rng, LANGS), pick(rng, REGIONS)
        cid = f"FBS-{500000 + i}"
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        phone = f"+1-{rng.randint(201, 989)}-555-{rng.randint(0, 9999):04d}"
        callers.append((cid, lang, region))
        con.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (cid, name, phone, "active", region, lang, "[]", "[]", "archive", "general"))
    drivers = {d[0]: d for d in DRIVERS}
    events = [(date.fromisoformat(e[1]), e[5], e[6], e[7]) for e in EVENTS]
    n, day = 0, START
    while day <= END:
        weekday = day.weekday()
        if weekday < 5:                                  # the archive is weekday contacts
            for dname, _team, weekly, handle, resolve_p, phrasings in DRIVERS:
                lam = weekly / 5
                for start, driver, peak, days in events:
                    age = (day - start).days
                    if driver == dname and 0 <= age < days:
                        lam += peak * math.exp(-3.0 * age / days)
                for _ in range(poisson(rng, lam * VOLUME)):
                    n += 1
                    cid, lang, region = rng.choice(callers)
                    slow = lang == SLOW_LANG
                    h = max(0.5, rng.gauss(handle * (1.35 if slow else 1.0), handle * 0.25))
                    resolved = rng.random() < resolve_p - (0.15 if slow else 0.0)
                    days_to = (rng.randint(1, 30) * (2 if slow else 1)) if resolved else None
                    promise = None
                    if rng.random() < 0.3:
                        due = day + timedelta(days=rng.choice([5, 10, 14, 30]))
                        kept = rng.random() >= BROKEN.get(dname, 0.08) if due <= END else None
                        promise = {"text": f"Call back with an answer by {due.isoformat()}", "dueAt": due.isoformat(),
                                   "kept": kept}
                    at = f"{day.isoformat()}T{rng.randint(8, 16):02d}:{rng.randint(0, 59):02d}"
                    con.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (f"c{n:06d}", cid, at, pick(rng, [("voicemail", 3), ("phone", 6), ("web", 1)]), dname,
                                 lang, region, round(h, 1), int(resolved), days_to, say(rng, phrasings),
                                 db.j(promise) if promise else None))
        day += timedelta(days=1)

    # PLANTED: callers stuck in loops: the same unresolved issue, again and again
    loops = 0
    for cid, lang, region in rng.sample(callers, int(len(callers) * LOOP_SHARE)):
        dname = rng.choice(["identity-check-hold", "appeal-status", "overpayment-notice", "form-22b-confusion"])
        d = drivers[dname]
        first = START + timedelta(days=rng.randint(0, (END - START).days - 120))
        for k in range(rng.randint(3, 6)):
            n += 1
            loops += 1
            at = first + timedelta(days=k * rng.randint(7, 21))
            con.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"c{n:06d}", cid, f"{at.isoformat()}T{rng.randint(8, 16):02d}:{rng.randint(0, 59):02d}",
                         "phone", dname, lang, region, round(max(0.5, rng.gauss(d[3] * 1.2, 1.5)), 1), 0, None,
                         say(rng, d[5]), None))
    # PLANTED, for the retroactive search: in the four weeks before today, callers said "error 4012" (the portal
    # outage that breaks out today) and were taken for password resets: never ticketed, overlooked. Their own
    # random stream, after everything else, so nothing above changes.
    orng = random.Random(f"overlooked:{seed_value}")
    said = ["The website keeps saying error 4012 when I try to log in.", "I get error 4012 every time I sign in.",
            "Your portal shows an error, 4012, and kicks me out.", "Sign-in fails with code 4012, I reset my password "
            "twice already.", "It says error four zero one two on the login page."]
    overlooked = []
    for _ in range(40):
        when = date(2026, 2, 9) + timedelta(days=orng.randint(0, 25))
        if when.weekday() >= 5:
            when -= timedelta(days=when.weekday() - 4)
        cid, lang, region = orng.choice(callers)
        n += 1
        overlooked.append(f"c{n:06d}")
        con.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"c{n:06d}", cid, f"{when.isoformat()}T{orng.randint(8, 16):02d}:{orng.randint(0, 59):02d}",
                     orng.choice(["phone", "voicemail"]), "password-reset", lang, region,
                     round(max(1.0, orng.gauss(4.0, 1.0)), 1), 1, 0, orng.choice(said), None))

    from overheard.memory.store import build as build_memory
    mem = build_memory(con, seed_value)          # routing memory, from the archive (deterministic)
    con.execute("INSERT INTO meta VALUES ('seed', ?)", (str(seed_value),))
    con.execute("INSERT INTO meta VALUES ('today', ?)", (today["date"],))
    con.execute("INSERT INTO meta VALUES ('overlooked', ?)", (json.dumps(overlooked),))  # the truth, for the mock
    con.commit()
    counts = {"voicemails": len(today["voicemails"]), "cases": len(today["cases"]) + len(callers),
              "contacts": n, "loop_contacts": loops, "events": len(EVENTS), **mem}
    con.close()
    return counts
