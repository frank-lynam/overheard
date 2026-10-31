"""The hand-written day carries the signals the demo depends on."""

import json
from importlib.resources import files

from overheard.data.models import Case, Voicemail

DAY = json.loads((files("overheard.data") / "seed_today.json").read_text(encoding="utf-8"))
VMS = [Voicemail(**v) for v in DAY["voicemails"]]
CASES = {c["id"]: Case(**c) for c in DAY["cases"]}


def test_sixty_in_order_with_ids():
    assert len(VMS) == 60
    assert [v.id for v in VMS] == [f"m{i:02d}" for i in range(1, 61)]
    assert [v.receivedAt for v in VMS] == sorted(v.receivedAt for v in VMS)


def test_the_urgent_one_is_buried_at_37():
    assert VMS[36].truth.urgency == 5 and VMS[36].truth.intent == "urgent_hardship"
    assert all(v.truth.urgency < 5 for v in VMS[:36])


def test_the_sign_in_wave():
    wave = [v for v in VMS if v.truth.group == "portal-sign-in"]
    assert len(wave) == 28 and wave[0].receivedAt.endswith("09:12")
    assert not any("outage" in v.script.lower() for v in VMS)


def test_languages_repeat_caller_and_obligations():
    assert sorted(v.lang for v in VMS if v.lang != "en") == ["es", "es-en", "tl", "vi"]
    assert all(v.truth.englishGist for v in VMS if v.lang != "en")
    whitfield = [v for v in VMS if v.truth.callerName == "Dolores Whitfield"]
    assert len(whitfield) == 3 and len({v.receivedAt[:10] for v in whitfield}) == 2
    assert all(len(v.truth.linkedTo) == 2 for v in whitfield)
    kinds = sorted(o for v in VMS for o in v.truth.obligations)
    assert kinds.count("congressional") == 2 and kinds.count("records") == 1 and kinds.count("legal") == 1
    assert "welfare" in kinds


def test_status_questions_are_answerable_from_the_case_system():
    status = [v for v in VMS if v.truth.resolvableBy == "status_lookup"]
    assert len(status) == 12
    for v in status:
        c = CASES[v.truth.caseId]
        assert c.payments or c.docs, v.id


def test_callers_without_a_case_number_are_findable_by_caller_id():
    unsaid = [v for v in VMS if not v.truth.caseNumberSaid and v.truth.caseId]
    assert len(unsaid) >= 6
    for v in unsaid:
        assert CASES[v.truth.caseId].phone == v.callerId, v.id
