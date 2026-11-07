"""The hand-written day carries the signals the demo depends on."""

import json
from importlib.resources import files

from overheard.data.models import Case, Voicemail

DAY = json.loads((files("overheard.data") / "seed_today.json").read_text(encoding="utf-8"))
ALL = [Voicemail(**v) for v in DAY["voicemails"]]
VMS = [v for v in ALL if v.id.startswith("m")]       # the 60 hand-written ones
JUNK = [v for v in ALL if v.id.startswith("j")]      # the 120 generated junk calls
CASES = {c["id"]: Case(**c) for c in DAY["cases"]}


def test_sixty_in_order_with_ids():
    assert len(VMS) == 60
    assert [v.id for v in VMS] == [f"m{i:02d}" for i in range(1, 61)]
    assert [v.receivedAt for v in VMS] == sorted(v.receivedAt for v in VMS)


def test_twice_as_much_junk_as_real_calls():
    assert len(JUNK) == 120 and [v.id for v in JUNK] == [f"j{i:03d}" for i in range(1, 121)]
    assert all(v.truth.junk for v in JUNK)
    real = [v for v in ALL if not v.truth.junk]
    assert len(real) == 59 and len(ALL) == 180          # one of the 60 was already a silent hang-up
    # robocalls and scams run a minute or so: listening to junk is real work in Mode 0
    assert sum(v.durationSec for v in JUNK if v.truth.junk in ("robocall", "scam")) / 60 > 50
    # a few real calls look like junk (a few words, a bad line)
    assert len([v for v in real if v.truth.looksLikeJunk]) >= 3


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
