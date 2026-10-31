"""Mode 3, view 1: cost by root cause. The archive is pre-labeled, so this is plain code
over `contacts`: Form 22-B must top the Pareto by agent-hours, at whatever share the
seed actually plants (tests check rank and share against the raw SQL baseline, not
absolute dollars — the centre is what it is, no scaling).

Offline: no LLM involved at all."""

import httpx
import pytest

from overheard.analytics.equity import equity_report
from overheard.analytics.events import event_impact
from overheard.analytics.journeys import repeat_callers
from overheard.analytics.promises import promise_outcomes
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


# --- view 3: caller journeys (repeat callers, loops) ----------------------

# the generator plants loops on exactly these four issues (see generator.py LOOP_SHARE)
PLANTED_LOOP_CAUSES = {"identity-check-hold", "appeal-status", "overpayment-notice", "form-22b-confusion"}


def test_journeys_recovers_the_planted_loops(seeded):
    _, con, counts = seeded
    report = repeat_callers(con)
    # the planted loop contacts are recovered within a sane band:
    # detection needs 3+ contacts per (caller, issue), so we should find the
    # bulk of the planted volume, no more than 10% extra
    planted = counts["loop_contacts"]
    assert planted > 1000  # the seed really planted loops
    assert report["loopContacts"] > 0.90 * planted
    assert report["loopContacts"] < 1.10 * planted
    # the top causes where loops start are exactly the planted four
    top4 = {c["cause"] for c in report["causes"][:4]}
    assert top4 == PLANTED_LOOP_CAUSES
    # planted loops never resolve, so every reported loop is stuck
    assert all(j["stuck"] for j in report["worst"])


def test_journeys_are_complete_and_ordered(seeded):
    _, con, _ = seeded
    report = repeat_callers(con)
    # every (case, issue) pair with 3+ contacts shows up exactly once
    raw = con.execute(
        "SELECT COUNT(*) FROM (SELECT case_id, root_cause FROM contacts GROUP BY case_id, root_cause "
        "HAVING COUNT(*) >= 3)"
    ).fetchone()[0]
    assert report["repeatJourneys"] == raw
    # the cause table covers every loop, in order of loop contacts
    assert sum(c["loops"] for c in report["causes"]) == report["loops"]
    contacts = [c["contacts"] for c in report["causes"]]
    assert contacts == sorted(contacts, reverse=True)
    assert sum(c["contacts"] for c in report["causes"]) == report["loopContacts"]
    # worst list is the ten biggest loops, and each really is a 3+ contact loop
    worst = report["worst"]
    assert len(worst) == 10
    assert worst[0]["contacts"] >= 3
    n = [j["contacts"] for j in worst]
    assert n == sorted(n, reverse=True)
    assert report["totalContacts"] > 60_000


async def test_api_journeys(client):
    r = await client.get("/api/archive/journeys")
    assert r.status_code == 200
    body = r.json()
    assert body["loops"] > 900
    assert body["causes"][0]["cause"] in PLANTED_LOOP_CAUSES
    assert all(j["contacts"] >= body["loopMinimum"] for j in body["worst"])


# --- view 4: promises vs. outcomes ---------------------------------------

# the generator plants broken-promise rates on these causes (see generator.py BROKEN)
PLANTED_BROKEN = {"appeal-status": 0.62, "claim-status": 0.35, "identity-check-hold": 0.45}
DEFAULT_BROKEN = 0.08


def test_promises_recover_the_planted_broken_rates(seeded):
    _, con, _ = seeded
    report = promise_outcomes(con)
    by_cause = {c["cause"]: c for c in report["causes"]}
    # each planted cause's broken rate must be within ~5 points of what was planted
    for cause, planted in PLANTED_BROKEN.items():
        c = by_cause[cause]
        assert c["settled"] >= 200, (cause, c)  # enough due promises for the rate to be meaningful
        assert abs(c["brokenRate"] - planted) < 0.05, (cause, c["brokenRate"], planted)
    # the causes with no planted rate sit near the default, pooled (small causes jitter on their own)
    default_causes = [c for c in by_cause.values() if c["cause"] not in PLANTED_BROKEN]
    kept = sum(c["kept"] for c in default_causes)
    settled = sum(c["settled"] for c in default_causes)
    assert settled >= 5000
    assert abs(kept / settled - (1 - DEFAULT_BROKEN)) < 0.02


def test_promises_are_complete(seeded):
    _, con, _ = seeded
    report = promise_outcomes(con)
    # the cause table accounts for every promise, and each cause partitions into kept/broken/pending
    assert sum(c["promises"] for c in report["causes"]) == report["totals"]["promises"]
    for c in report["causes"]:
        assert c["kept"] + c["broken"] + c["pending"] == c["promises"], c
    assert (
        report["totals"]["kept"] + report["totals"]["broken"] + report["totals"]["pending"]
        == report["totals"]["promises"]
    )
    # the team table covers the same promises as the cause table
    assert sum(t["promises"] for t in report["teams"]) == report["totals"]["promises"]
    # the raw archive really did plant promises on roughly 30% of contacts
    n_promise = con.execute("SELECT COUNT(*) FROM contacts WHERE promise IS NOT NULL").fetchone()[0]
    n_contacts = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    assert abs(report["promiseShare"] - n_promise / n_contacts) < 0.01
    assert report["totals"]["promises"] == n_promise


def test_promises_team_breakdown(seeded):
    _, con, _ = seeded
    report = promise_outcomes(con)
    # the archive is one team; the report should say so and be internally consistent
    teams = {t["team"] for t in report["teams"]}
    assert teams == {"general"}, teams
    g = report["teams"][0]
    assert g["kept"] + g["broken"] + g["pending"] == g["promises"]
    assert g["brokenRate"] == report["totals"]["brokenRate"]


async def test_api_promises(client):
    r = await client.get("/api/archive/promises")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["promises"] > 10_000
    assert 0 < body["promiseShare"] < 1
    top = {c["cause"]: c["brokenRate"] for c in body["causes"]}
    assert top["appeal-status"] == max(top.values())  # the worst offender is the planted worst cause
    assert body["worstOffender"]["cause"] == "appeal-status"


PLANTED_SLOW_LANG = "vi"
PLANTED_WAIT_RATIO = 1.35  # the generator scales the slow language's handle time by this


def test_equity_flags_the_planted_slow_language(seeded):
    _, con, _ = seeded
    report = equity_report(con)
    langs = {r["name"]: r for r in report["languages"]}
    # vi is the slowest language by a real margin
    assert report["worstLanguage"]["slow"] == PLANTED_SLOW_LANG
    others = [r["avgWaitMin"] for n, r in langs.items() if n != PLANTED_SLOW_LANG]
    assert langs[PLANTED_SLOW_LANG]["avgWaitMin"] > max(others) * 1.1
    # the wait gap is within ~10% of the planted 1.35x (gaussian noise wobbles it a bit)
    ratio = report["worstLanguage"]["waitRatio"]
    assert 1.25 <= ratio <= 1.45, (ratio, PLANTED_WAIT_RATIO)
    # the planted resolution penalty (~15 points) and doubled time-to-resolution show up
    fast = report["worstLanguage"]["fastResolveRate"]
    slow = report["worstLanguage"]["slowResolveRate"]
    assert 0.10 <= fast - slow <= 0.20, (fast, slow)
    assert langs[PLANTED_SLOW_LANG]["avgDaysToResolve"] > 1.7 * max(
        r["avgDaysToResolve"] for n, r in langs.items() if n != PLANTED_SLOW_LANG
    )


def test_equity_is_complete(seeded):
    _, con, _ = seeded
    report = equity_report(con)
    total = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    assert report["totalContacts"] == total
    assert sum(r["contacts"] for r in report["languages"]) == total
    assert sum(r["contacts"] for r in report["channels"]) == total
    # group means agree with the raw SQL baseline
    for lang, m in con.execute("SELECT lang, AVG(handle_min) FROM contacts GROUP BY lang"):
        row = next(r for r in report["languages"] if r["name"] == lang)
        assert row["avgWaitMin"] == round(m, 2), (lang, row, m)
    # channels are the archive's three, nothing invented
    assert {r["name"] for r in report["channels"]} == {"voicemail", "phone", "web"}


async def test_api_equity(client):
    r = await client.get("/api/archive/equity")
    assert r.status_code == 200
    body = r.json()
    assert body["totalContacts"] > 50_000
    assert body["worstLanguage"]["slow"] == PLANTED_SLOW_LANG
    assert body["worstLanguage"]["waitRatio"] > 1.2


# --- Mode 3, view 6: the letter lab -------------------------------------------

from overheard.analytics.letter_lab import (  # noqa: E402
    clarity_report,
    detect_notice,
    letter_lab,
    mailing_windows,
    rewrite_letter,
)

LL_22B_DRAFT = (
    "Dear Claimant, we have made a determination that your records require re-verification of your "
    "address and income. Pursuant to our prescribed regulations, subject to further review, your "
    "benefits will be stopped if the re-verification documentation is not returned to us within 30 days. "
    "If you fail to return the documentation, your payment may be suspended and you may owe back "
    "benefits for the months in which no re-verification was on file at all."
)

LL_COLA_DRAFT = (
    "Dear Claimant, your payment has changed because of the annual cost-of-living adjustment. "
    "Here is your new amount for this year."
)


def test_letterlab_detects_the_planted_22b_letter(seeded):
    _, con, _ = seeded
    det = detect_notice(LL_22B_DRAFT)
    assert det["driver"] == PLANTED_TOP  # the 22-B re-verification draft sounds like the 22-B
    assert "re-verify" in " ".join(det["matchedWords"]) or len(det["matchedWords"]) >= 3
    det_cola = detect_notice(LL_COLA_DRAFT)
    assert det_cola["driver"] == "cola-letter"


def test_letterlab_predicts_the_planted_22b_volume(seeded):
    _, con, _ = seeded
    result = letter_lab(con, LL_22B_DRAFT)
    windows = result["predicted"]["perMailing"]
    assert len(windows) == 4  # the archive holds four 22-B mailings
    excesses = [w["excess"] for w in windows]
    assert all(e > 0 for e in excesses)  # each mailing really did spike over baseline
    low, mid, high = (result["predicted"][k] for k in ("low", "mid", "high"))
    assert low <= mid <= high
    # the mid sits within ~25% of the archive's measured excesses (the clarity scale nudges it)
    assert max(excesses) * 0.75 <= mid <= max(excesses) * 1.25
    assert low > 0


def test_letterlab_rewrite_is_clearer_and_cheaper(seeded):
    _, con, _ = seeded
    before = clarity_report(LL_22B_DRAFT)
    after = clarity_report(rewrite_letter(LL_22B_DRAFT))
    assert after["score"] > before["score"]
    assert after["hasDeadline"] and after["hasAction"]
    result = letter_lab(con, LL_22B_DRAFT)
    r = result["rewrite"]
    assert r["clarityScore"] > result["clarity"]["score"]
    assert r["questionsBefore"] > 0
    assert r["questionsAfter"] < r["questionsBefore"]
    assert 0 < r["reductionPct"] < 1
    # the rewrite kept the point: the 22-B is still detectable in it
    assert detect_notice(r["text"])["driver"] == PLANTED_TOP


def test_letterlab_shows_real_archive_questions(seeded):
    _, con, _ = seeded
    result = letter_lab(con, LL_22B_DRAFT)
    q = result["archiveQuestions"]
    assert q["count"] > 100  # a year of 22-B mailings means plenty of real contacts
    assert len(q["sample"]) == 6
    for s in q["sample"]:
        assert s["channel"] in {"voicemail", "phone", "web"}
        assert " " in s["text"]


def test_letterlab_windows_match_event_impact(seeded):
    _, con, _ = seeded
    windows = mailing_windows(con, PLANTED_TOP)
    impact = {e["id"]: e for e in event_impact(con)}
    for w in windows:
        assert impact[w["event"]]["count"] == w["count"]
        assert impact[w["event"]]["excess"] == w["excess"]


async def test_api_letterlab(client):
    r = await client.post("/api/archive/letter-lab", json={"text": LL_22B_DRAFT})
    assert r.status_code == 200
    body = r.json()
    assert body["detected"]["driver"] == PLANTED_TOP
    assert len(body["predicted"]["perMailing"]) == 4
    assert body["rewrite"]["clarityScore"] > body["clarity"]["score"]
    assert "what to do" in body["rewrite"]["text"].lower()
