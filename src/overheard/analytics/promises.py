"""View 4 of Mode 3: promises vs. outcomes.

The archive's contacts carry callback promises: a due date and, once that date
has passed, whether the promise was kept (true/false); a promise whose due date
falls after the archive's end is still pending (null). This view counts, per
root cause and per team, how many of the centre's promises were kept, broken,
or are still open, and the broken rate within the settled ones. Plain code
over `contacts.promise` + `cases.team`; no LLM.
"""

import json
import sqlite3
from datetime import date, timedelta


def _archive_end(con: sqlite3.Connection) -> date:
    """The day after the archive's last contact day: the pending horizon."""
    last = con.execute("SELECT MAX(at) FROM contacts").fetchone()[0]
    return date.fromisoformat(last[:10]) + timedelta(days=1)


def _outcomes(con: sqlite3.Connection) -> dict[str, dict]:
    """Per root cause: {promises, kept, broken, pending} over settled+open promises."""
    end = _archive_end(con)
    out: dict[str, dict] = {}
    for cause, promise in con.execute("SELECT root_cause, promise FROM contacts WHERE promise IS NOT NULL"):
        p = json.loads(promise)
        row = out.setdefault(cause, {"promises": 0, "kept": 0, "broken": 0, "pending": 0})
        row["promises"] += 1
        if p.get("dueAt", "") < end.isoformat():
            if p.get("kept"):
                row["kept"] += 1
            else:
                row["broken"] += 1
        else:
            row["pending"] += 1
    return out


def promise_outcomes(con: sqlite3.Connection) -> dict:
    """The promises view: broken-promise rates by cause and by team, plus totals."""
    end = _archive_end(con)
    per_cause = _outcomes(con)

    # per team: join the promise row to the caller's case
    per_team: dict[str, dict] = {}
    for team, promise in con.execute(
        "SELECT c.team, ct.promise FROM contacts ct JOIN cases c ON c.id = ct.case_id WHERE ct.promise IS NOT NULL"
    ):
        p = json.loads(promise)
        row = per_team.setdefault(team, {"promises": 0, "kept": 0, "broken": 0, "pending": 0})
        row["promises"] += 1
        if p.get("dueAt", "") < end.isoformat():
            if p.get("kept"):
                row["kept"] += 1
            else:
                row["broken"] += 1
        else:
            row["pending"] += 1

    def rates(row: dict) -> dict:
        settled = row["kept"] + row["broken"]
        broken_rate = row["broken"] / settled if settled else 0.0
        row = dict(row)
        row["settled"] = settled
        row["brokenRate"] = round(broken_rate, 4)
        row["keptRate"] = round(1 - broken_rate, 4) if settled else None
        return row

    causes = sorted(({"cause": c, **rates(r)} for c, r in per_cause.items()), key=lambda r: (-r["brokenRate"], -r["broken"]))
    teams = sorted(({"team": t, **rates(r)} for t, r in per_team.items()), key=lambda r: -r["promises"])

    totals = {"promises": 0, "kept": 0, "broken": 0, "pending": 0}
    for r in per_cause.values():
        for k in totals:
            totals[k] += r[k]
    totals = rates(totals)
    total_contacts = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    return {
        "archiveEnd": end.isoformat(),
        "totalContacts": total_contacts,
        "promiseShare": round(totals["promises"] / total_contacts, 4) if total_contacts else 0.0,
        "totals": totals,
        "worstOffender": causes[0] if causes else None,
        "causes": causes,
        "teams": teams,
    }
