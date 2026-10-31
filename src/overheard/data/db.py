"""SQLite: the seeded day, the case system, and the archive. Nested lists (payments, docs) are stored as JSON."""

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE voicemails (id TEXT PRIMARY KEY, received_at TEXT, caller_id TEXT, duration_sec INTEGER, lang TEXT,
                         script TEXT, truth TEXT);
CREATE TABLE cases (id TEXT PRIMARY KEY, name TEXT, phone TEXT, status TEXT, region TEXT, lang TEXT, payments TEXT,
                    docs TEXT, last_action TEXT, team TEXT);
CREATE INDEX cases_phone ON cases (phone);
CREATE TABLE events (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, description TEXT);
CREATE TABLE contacts (id TEXT PRIMARY KEY, case_id TEXT, at TEXT, channel TEXT, root_cause TEXT, lang TEXT, region TEXT,
                       handle_min REAL, resolved INTEGER, days_to_resolve INTEGER, text TEXT, promise TEXT);
CREATE INDEX contacts_case ON contacts (case_id);
CREATE INDEX contacts_cause ON contacts (root_cause, at);
CREATE TABLE kb_articles (id TEXT PRIMARY KEY, title TEXT, body TEXT, topics TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def create(path: Path | str) -> sqlite3.Connection:
    """A fresh database at `path` (an existing one is replaced)."""
    path = Path(path)
    if path.exists():
        path.unlink()
    con = connect(path)
    con.executescript(SCHEMA)
    return con


def dump_digest(con: sqlite3.Connection) -> str:
    """A digest of every row, for checking that the same seed gives the same data."""
    import hashlib

    h = hashlib.sha256()
    for line in con.iterdump():
        h.update(line.encode())
    return h.hexdigest()


def j(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
