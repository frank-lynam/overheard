import sqlite3

import pytest

from overheard.data.generator import seed


@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    """One seeded database for the whole run (seeding takes a couple of seconds)."""
    path = tmp_path_factory.mktemp("db") / "overheard.db"
    counts = seed(path, 2026)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    yield path, con, counts
    con.close()
