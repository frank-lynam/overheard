"""Code-word alerts: the trigger list, the matcher, alerts raised before anything else, and the API."""

import httpx
import pytest

from overheard.app import create_app
from overheard.config import Settings
from overheard.data.models import Voicemail
from overheard.pipeline.intake import intake
from overheard.triggers import TriggerList, default_list

#: the code words planted in the seeded day
PLANTED = {"m09": {"attorney", "legal action"}, "m16": {"congresswoman"}, "m37": {"shut off"}, "m53": {"senator"}}


def vm(script, id_="x1"):
    return Voicemail(id=id_, receivedAt="2026-03-10T09:00:00", callerId="+15550000000", durationSec=30, lang="en",
                     script=script, truth={"intent": "other", "urgency": 2, "team": "general", "rootCause": "other",
                                           "callerName": None, "callbackNumber": "+15550000000", "caseId": None,
                                           "obligations": [], "resolvableBy": None})


def test_the_list_loads_and_says_its_illustrative():
    tl = default_list()
    assert tl.illustrative and "illustrative" in tl.note
    assert tl.categories["safety"]["priority"] < tl.categories["legal"]["priority"]


def test_each_planted_trigger_is_found(seeded):
    _, con, _ = seeded
    tl = default_list()
    found = {}
    for r in con.execute("SELECT id, script FROM voicemails"):
        hits = tl.scan(r["script"])
        if hits:
            found[r["id"]] = {h.term for h in hits}
    assert found == PLANTED


def test_variants_match_only_when_configured():
    tl = TriggerList({"categories": {"legal": {"priority": 1, "label": "Legal"}},
                      "terms": [{"term": "lawyer", "category": "legal", "variants": ["lawyers"]},
                                {"term": "sue", "category": "legal"}]})
    assert [h.term for h in tl.scan("Two LAWYERS called")] == ["lawyer"]        # a configured variant
    assert tl.scan("they lawyered up") == []                                    # an unconfigured one
    assert tl.scan("there's an issue with suing them") == []                    # word boundaries
    assert [h.said for h in tl.scan("I will Sue.")] == ["Sue"]


def test_an_alert_is_raised_before_any_later_stage():
    seen = []
    it = intake(vm("My attorney says to call."), later=[("problem check", lambda i: seen.append(list(i.log)))])
    assert it.log == ["transcript", "alert", "problem check start"]
    assert seen == [["transcript", "alert", "problem check start"]]           # the alert was already up
    assert it.alert["category"] == "legal" and it.alert_ms is not None


def test_a_safety_hit_is_top_priority_and_would_page_someone():
    it = intake(vm("I can't take this, I might hurt myself, and my lawyer won't call back."))
    assert it.alert["safety"] and it.alert["priority"] == 0
    assert it.alert["page"] == "would page: duty supervisor (simulated)"
    assert [h["category"] for h in it.alert["hits"]] == ["safety", "legal"]


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_alerts_api_is_off_in_mode_0_and_on_from_mode_1(client):
    assert (await client.get("/api/alerts", params={"mode": 0})).json()["alerts"] == []
    got = (await client.get("/api/alerts", params={"mode": 1})).json()
    assert {a["id"] for a in got["alerts"]} == set(PLANTED) and got["illustrative"]
    assert all(a["alertMs"] is not None for a in got["alerts"])
    msg = (await client.get("/api/messages/m16", params={"mode": 1})).json()
    assert msg["alert"]["hits"][0]["said"] == "Congresswoman"                 # its span, for the highlight
