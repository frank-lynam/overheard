"""The generated archive: deterministic, about the planned size, and its planted patterns recoverable."""

import sqlite3

from overheard.data import db
from overheard.data.generator import seed


def q(con, sql, *args):
    return con.execute(sql, args).fetchall()


def test_same_seed_same_data_other_seed_other_data(seeded, tmp_path):
    path, con, _ = seeded
    again = tmp_path / "again.db"
    other = tmp_path / "other.db"
    seed(again, 2026)
    seed(other, 7)
    digest = db.dump_digest(con)
    assert db.dump_digest(sqlite3.connect(again)) == digest
    assert db.dump_digest(sqlite3.connect(other)) != digest


def test_size(seeded):
    _, _, counts = seeded
    assert 60_000 <= counts["contacts"] <= 80_000, counts


def test_form_22b_costs_the_most(seeded):
    _, con, _ = seeded
    top = q(con, "SELECT root_cause FROM contacts GROUP BY 1 ORDER BY sum(handle_min) DESC LIMIT 1")[0][0]
    assert top == "form-22b-confusion"


def test_portal_42_spike(seeded):
    _, con, _ = seeded
    during = q(con, "SELECT count(*) FROM contacts WHERE root_cause='portal-sign-in-failure' "
                    "AND at BETWEEN '2025-05-06' AND '2025-05-15'")[0][0]
    before = q(con, "SELECT count(*) FROM contacts WHERE root_cause='portal-sign-in-failure' "
                    "AND at BETWEEN '2025-04-20' AND '2025-04-29'")[0][0]
    assert during >= 8 * max(before, 1), (during, before)


def test_one_language_is_served_worse(seeded):
    _, con, _ = seeded
    rows = {r[0]: r[1] for r in q(con, "SELECT lang, avg(days_to_resolve) FROM contacts GROUP BY 1")}
    assert rows["vi"] > 1.6 * rows["en"], rows


def test_broken_promises_concentrate_in_appeals(seeded):
    _, con, _ = seeded
    kept = q(con, "SELECT root_cause FROM contacts WHERE promise IS NOT NULL AND json_extract(promise,'$.kept') "
                  "IS NOT NULL GROUP BY 1 HAVING count(*) >= 30 ORDER BY avg(json_extract(promise,'$.kept')) LIMIT 1")
    assert kept[0][0] == "appeal-status"


def test_weak_signal_before_the_spike(seeded):
    _, con, _ = seeded
    trickle = q(con, "SELECT count(*) FROM contacts WHERE root_cause='tax-form-1099' "
                     "AND at BETWEEN '2024-10-01' AND '2025-01-20'")[0][0]
    quiet = q(con, "SELECT count(*) FROM contacts WHERE root_cause='tax-form-1099' "
                   "AND at BETWEEN '2023-10-01' AND '2024-01-20'")[0][0]
    spike = q(con, "SELECT count(*) FROM contacts WHERE root_cause='tax-form-1099' "
                   "AND at BETWEEN '2025-01-27' AND '2025-02-15'")[0][0]
    assert trickle > quiet and spike > 3 * trickle, (quiet, trickle, spike)


def test_callers_stuck_in_loops(seeded):
    _, con, _ = seeded
    stuck = q(con, "SELECT count(*) FROM (SELECT case_id FROM contacts WHERE resolved=0 GROUP BY case_id, root_cause "
                   "HAVING count(*) >= 3)")[0][0]
    assert stuck >= 600
