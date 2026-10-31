"""Mode 3, view 1: cost by root cause. The archive is pre-labeled, so this is plain code
over `contacts`: Form 22-B must top the Pareto by agent-hours, at whatever share the
seed actually plants (tests check rank and share against the raw SQL baseline, not
absolute dollars — the centre is what it is, no scaling).

Offline: no LLM involved at all."""

import httpx
import pytest

from overheard.analytics.events import event_impact
from overheard.analytics.root_causes import root_causes
from overheard.app import create_app
from overheard.config import Settings
from overheard.data.events import EVENTS

PLANTED_TOP = "form-22b-confusion"  # the four mailings in events.py drive a large, slow-fading excess


@pytest.fixture
async def client(seeded):
    app = create_app(Settings(db_path=seeded[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


def test_pareto_tops_on_form_22b(seeded):
    _, con, _ = seeded
    report = root_causes(con)
    assert report["causes"][0]["cause"] == PLANTED_TOP
    # share must match the raw SQL baseline within 10%
    total = con.execute("SELECT SUM(handle_min) FROM contacts").fetchone()[0]
    planted = con.execute("SELECT SUM(handle_min) FROM contacts WHERE root_cause=?", (PLANTED_TOP,)).fetchone()[0]
    assert abs(report["causes"][0]["share"] - planted / total) < 0.10 * planted / total


def test_pareto_is_complete_and_ordered(seeded):
    _, con, _ = seeded
    report = root_causes(con)
    assert sum(c["contacts"] for c in report["causes"]) == con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    assert abs(sum(c["share"] for c in report["causes"]) - 1.0) < 0.01
    hours = [c["hours"] for c in report["causes"]]
    assert hours == sorted(hours, reverse=True)
    assert report["causes"][-1]["cumShare"] == pytest.approx(1.0, abs=0.01)
    assert 1 <= report["top80Count"] < len(report["causes"])  # a real Pareto: few causes, most of the cost


def test_cost_model_scales_with_the_labor_rate(seeded):
    _, con, _ = seeded
    cheap = root_causes(con, labor_rate=10.0)
    pricey = root_causes(con, labor_rate=100.0)
    assert pricey["annualCostUsd"] == pytest.approx(cheap["annualCostUsd"] * 10, rel=0.01)
    assert cheap["causes"][0]["annualCostUsd"] == pytest.approx(cheap["causes"][0]["hours"] * 3 * 10, rel=0.01)
    # hours and shares don't care about dollars
    assert [c["hours"] for c in cheap["causes"]] == [c["hours"] for c in pricey["causes"]]


async def test_api_root_causes(client):
    r = await client.get("/api/archive/root-causes")
    assert r.status_code == 200
    body = r.json()
    assert body["causes"][0]["cause"] == PLANTED_TOP
    assert body["totalContacts"] > 60_000
    assert 0.0 < body["causes"][0]["share"] < 1.0
    assert body["laborRate"] > 0


# --- view 2: event impact -----------------------------------------------

PLANTED_TOP_EVENT = "ev-22b-1"  # the loudest planted spike (verified on the seed)
PLANTED_QUIET = "ev-1099-quiet"  # a vendor change that should NOT move the volume
PLANTED_RELEASE = "ev-portal-42"  # a release that does move the volume


def test_event_impact_recovers_the_planted_spikes(seeded):
    _, con, _ = seeded
    report = event_impact(con)
    by_id = {e["id"]: e for e in report}
    assert report[0]["id"] == PLANTED_TOP_EVENT
    assert report[0]["driver"] == PLANTED_TOP  # the 22-B mailings drive the loudest window
    # the loud release lands near the top, the quiet policy change lands near the bottom
    assert report.index(by_id[PLANTED_RELEASE]) < len(report) // 2
    assert report.index(by_id[PLANTED_QUIET]) >= len(report) - 4
    assert by_id[PLANTED_QUIET]["excess"] < by_id[PLANTED_TOP_EVENT]["excess"] / 10


def test_event_impact_is_complete_and_ordered(seeded):
    _, con, _ = seeded
    report = event_impact(con)
    assert len(report) == len(EVENTS)  # every event on the calendar is scored
    excess = [e["excess"] for e in report]
    assert excess == sorted(excess, reverse=True)
    for e in report:
        assert e["count"] >= 0 and e["expected"] >= 0
        assert e["excess"] >= 0 and e["count"] >= e["expected"] - 1  # excess means "above expected"
        assert e["hours"] >= 0 and e["excessHours"] >= 0
    assert abs(sum(e["excessShare"] for e in report) - 100.0) < 1.0  # shares add up


def test_event_impact_baseline_is_the_causes_own(seeded):
    # a slow cause (tax-form-1099) must not be mistaken for a loud one: its expected
    # contacts are measured against its own weekday rate, not the archive average
    _, con, _ = seeded
    report = {e["id"]: e for e in event_impact(con)}
    quiet = report[PLANTED_QUIET]
    total = con.execute("SELECT COUNT(*) FROM contacts WHERE root_cause=?", (quiet["driver"],)).fetchone()[0]
    assert quiet["baselinePerDay"] == pytest.approx(total / 730, rel=0.5)  # ballpark, not a re-derivation


async def test_api_event_impact(client):
    r = await client.get("/api/archive/event-impact")
    assert r.status_code == 200
    body = r.json()
    assert len(body["events"]) == len(EVENTS)
    assert body["events"][0]["id"] == PLANTED_TOP_EVENT
    assert body["events"][0]["excess"] > 0
