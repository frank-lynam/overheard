"""View 3 of Mode 3: caller journeys — who is stuck in a loop, and where loops start.

A journey is everything one caller (case) said about one issue (root cause), linked
across the whole archive. A loop is a journey with three or more contacts whose
latest contact is still unresolved: the caller keeps calling about the same thing
and no one has closed it. Plain SQL over the pre-labeled archive.
"""

import sqlite3
from datetime import date

LOOP_MIN = 3


def _journeys(con: sqlite3.Connection) -> list[dict]:
    """Every (case, cause) pair with at least LOOP_MIN contacts, with its outcome.

    The outcome is the latest contact: if that one is unresolved, the caller is
    still in the loop even if earlier contacts happened to resolve.
    """
    rows = con.execute(
        "SELECT case_id, root_cause, COUNT(*) AS n, MIN(at) AS first_at, MAX(at) AS last_at, "
        "SUM(handle_min) AS minutes, "
        "SUM(CASE WHEN at = max_at THEN resolved ELSE 0 END) AS last_resolved "
        "FROM (SELECT c.*, MAX(at) OVER (PARTITION BY case_id, root_cause) AS max_at FROM contacts c) "
        "GROUP BY case_id, root_cause HAVING COUNT(*) >= ?",
        (LOOP_MIN,),
    ).fetchall()
    out = []
    for case_id, cause, n, first, last, minutes, last_resolved in rows:
        out.append(
            {
                "caseId": case_id,
                "cause": cause,
                "contacts": n,
                "first": first,
                "last": last,
                "hours": round((minutes or 0) / 60.0, 1),
                "days": (date.fromisoformat(last[:10]) - date.fromisoformat(first[:10])).days,
                "stuck": not last_resolved,
            }
        )
    return out


def repeat_callers(con: sqlite3.Connection) -> dict:
    """The journey view: repeat callers, the loops among them, and where loops start."""
    journeys = _journeys(con)
    loops = [j for j in journeys if j["stuck"]]
    loops.sort(key=lambda j: (-j["contacts"], -j["days"]))

    by_cause: dict[str, dict] = {}
    for j in loops:
        row = by_cause.setdefault(j["cause"], {"cause": j["cause"], "loops": 0, "contacts": 0, "hours": 0.0})
        row["loops"] += 1
        row["contacts"] += j["contacts"]
        row["hours"] = round(row["hours"] + j["hours"], 1)
    causes = sorted(by_cause.values(), key=lambda r: -r["contacts"])

    total_contacts = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return {
        "loopMinimum": LOOP_MIN,
        "totalContacts": total_contacts,
        "repeatJourneys": len(journeys),
        "loops": len(loops),
        "loopContacts": sum(j["contacts"] for j in loops),
        "loopHours": round(sum(j["hours"] for j in loops), 1),
        "causes": causes,
        "worst": loops[:10],
    }
