"""The mock case system, over the seeded database."""

import json
import re
import sqlite3

from overheard.data.models import Case


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


class MockCaseBackend:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def _case(self, row) -> Case:
        return Case(id=row["id"], name=row["name"], phone=row["phone"], status=row["status"], region=row["region"],
                    lang=row["lang"], payments=json.loads(row["payments"]), docs=json.loads(row["docs"]),
                    lastAction=row["last_action"], team=row["team"])

    def case(self, case_id: str) -> Case | None:
        cid = case_id.upper().replace(" ", "")
        if not cid.startswith("FBS-"):
            cid = "FBS-" + _digits(cid)
        row = self.con.execute("SELECT * FROM cases WHERE id = ?", (cid,)).fetchone()
        return self._case(row) if row else None

    def by_phone(self, phone: str) -> list[Case]:
        want = _digits(phone)[-10:]
        rows = self.con.execute("SELECT * FROM cases").fetchall() if want else []
        return [self._case(r) for r in rows if _digits(r["phone"])[-10:] == want]

    def search(self, text: str) -> list[Case]:
        """Name, phone or case number, the way an agent types into the lookup box."""
        text = text.strip()
        if not text:
            return []
        if _digits(text) and len(_digits(text)) >= 6:
            found = self.by_phone(text) if len(_digits(text)) >= 10 else []
            c = self.case(text)
            return found + ([c] if c and c not in found else [])
        rows = self.con.execute("SELECT * FROM cases WHERE name LIKE ? ORDER BY name LIMIT 20", (f"%{text}%",))
        return [self._case(r) for r in rows]
