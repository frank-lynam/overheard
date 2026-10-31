"""The mock case system answers what an agent would look up."""

import json

from overheard.adapters.backend.mock import MockCaseBackend


def test_lookups(seeded):
    _, con, _ = seeded
    be = MockCaseBackend(con)
    assert be.case("FBS-311902").name == "Marcus Bell"
    assert be.case("311902").id == "FBS-311902"                     # how it's said on the phone
    assert be.case("nope") is None
    assert [c.id for c in be.by_phone("(216) 555-0188")] == ["FBS-190455"]
    assert any(c.id == "FBS-104227" for c in be.search("Whitfield"))
    assert be.search("FBS 104227")[0].id == "FBS-104227"


def test_every_voicemail_with_a_case_finds_it(seeded):
    _, con, _ = seeded
    be = MockCaseBackend(con)
    for row in con.execute("SELECT id, caller_id, truth FROM voicemails"):
        truth = json.loads(row["truth"])
        if truth["caseId"]:
            assert be.case(truth["caseId"]) is not None, row["id"]
            if not truth["caseNumberSaid"]:
                assert truth["caseId"] in [c.id for c in be.by_phone(row["caller_id"])], row["id"]
