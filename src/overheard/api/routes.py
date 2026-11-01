"""The REST API: the day's queue, a message, case lookups, manual entries, the simulation, the assumptions."""

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from overheard.adapters.backend.mock import MockCaseBackend
from overheard.data.models import Case, Voicemail
from overheard.pipeline.analyze import AnalysisDeps, analyze, analyze_sync, team_of, urgency_of
from overheard.pipeline.mode2 import Mode2Deps, _message_mode2, day_bundles, message_mode2, scoreboard2
from overheard.pipeline.simulate import Assumptions, Simulation, work_the_queue

router = APIRouter(prefix="/api")

#: marks a field nobody corrected, so a correction to `null` is not confused with no correction
_UNCORRECTED = object()


def con(request: Request) -> sqlite3.Connection:
    return request.app.state.db.get()


def deps(request: Request) -> AnalysisDeps:
    # Sync routes run in worker threads, each with its own connection; the analysis is
    # serialized on a per-app lock, and bundles are cached per message.
    return AnalysisDeps(
        con=con(request),
        lock=request.app.state.analyze_lock,
        cache=request.app.state.analysis_cache,
        store=request.app.state.store,
        provider=request.app.state.provider,
        model=request.app.state.settings.llm_model or "mock",
        write=request.app.state.settings.llm_mode == "record",
    )


def voicemails(request: Request) -> list[Voicemail]:
    rows = con(request).execute("SELECT * FROM voicemails ORDER BY received_at, id").fetchall()
    return [Voicemail(id=r["id"], receivedAt=r["received_at"], callerId=r["caller_id"], durationSec=r["duration_sec"],
                      lang=r["lang"], script=r["script"], truth=json.loads(r["truth"])) for r in rows]


class QueueItem(BaseModel):
    id: str
    receivedAt: str
    callerId: str
    durationSec: int
    worked: bool


class Mode1Item(QueueItem):
    urgency: int
    team: str


class Mode2Item(QueueItem):
    urgency: int
    team: str
    clusterSize: int = 1
    repeat: dict | None = None  # the collapse note when this leads a repeat-caller group
    incident: str | None = None  # the incident title, when this message is in the spike
    resolvable: bool | None = None
    obligation: str | None = None  # the first obligation kind, for the badge
    window: str | None = None  # the callback window the caller gave


def mode2_day(request: Request) -> dict:
    """The day's mode-2 computation, once: groups, repeats, missing-info, incidents."""
    with request.app.state.mode2_lock:
        if request.app.state.mode2 is None:
            d = deps(request)
            vms = voicemails(request)
            bundles = {v.id: analyze_sync(v, d) for v in vms}
            backend = MockCaseBackend(con(request))
            request.app.state.mode2 = day_bundles(vms, bundles, backend, Mode2Deps(d.con, d.store, d.provider, d.model))
    return request.app.state.mode2


def mode2_messages(request: Request) -> dict:
    """Each message's mode-2 section, once (what the queue shows of it doesn't change during the day)."""
    mode2_day(request)  # the day first: the queue needs both, and the warm-up computes them together
    with request.app.state.mode2_lock:
        if request.app.state.mode2_messages is None:
            d = deps(request)
            backend = MockCaseBackend(con(request))
            mdeps = Mode2Deps(d.con, d.store, d.provider, d.model)
            request.app.state.mode2_messages = {
                v.id: message_mode2(v, analyze_sync(v, d), backend, mdeps) for v in voicemails(request)
            }
    return request.app.state.mode2_messages


class Message(BaseModel):
    id: str
    receivedAt: str
    callerId: str
    durationSec: int
    lang: str
    script: str
    words: int


class ManualEntry(BaseModel):
    callerName: str = ""
    callbackNumber: str = ""
    caseNumber: str = ""
    category: str = ""
    priority: int | None = None
    notes: str = ""
    disposition: str = ""
    secondsSpent: float = 0


@router.get("/day")
def day(request: Request) -> dict:
    return {"date": request.app.state.today, "count": len(voicemails(request))}


@router.get("/queue")
def queue(request: Request, mode: int = 0) -> list[QueueItem] | list[Mode1Item] | list[Mode2Item]:
    """Mode 0's inbox: when, who, how long; no content until it's played.
    Mode 1: the same inbox ordered by the AI's urgency, with the routed team.
    Mode 2: the same, plus the day's cross-message reasoning: cluster size,
    collapsed repeat callers, the incident, resolvable, obligations, windows."""
    if mode == 0:
        worked = {r[0] for r in con(request).execute("SELECT id FROM entries")}
        return [QueueItem(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                          worked=v.id in worked) for v in voicemails(request)]
    d = deps(request)
    vms = voicemails(request)
    bundles = {v.id: analyze_sync(v, d) for v in vms}
    if mode == 1:
        worked = {r[0] for r in d.con.execute("SELECT id FROM entries")}
        items = [
            Mode1Item(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                      worked=v.id in worked, urgency=urgency_of(bundles[v.id]), team=team_of(bundles[v.id]))
            for v in vms
        ]
        items.sort(key=lambda i: (-i.urgency, i.receivedAt, i.id))
        return items
    day = mode2_day(request)
    sections = mode2_messages(request)
    cluster_of: dict[str, int] = {}
    for members in day["clusters"].values():
        for mid in members:
            cluster_of[mid] = len(members)
    incident_members: dict[str, str] = {}
    for inc in day["incidents"]:
        for mid in inc["members"]:
            incident_members[mid] = inc["card"]["title"]
    worked = {r[0] for r in d.con.execute("SELECT id FROM entries")}
    items = []
    for v in vms:
        m2 = sections[v.id]
        o = m2["resolution"]
        obligations = m2["obligations"]
        items.append(
            Mode2Item(
                id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                worked=v.id in worked, urgency=urgency_of(bundles[v.id]), team=team_of(bundles[v.id]),
                clusterSize=cluster_of.get(v.id, 1),
                repeat=day["repeats"].get(v.id),
                incident=incident_members.get(v.id),
                resolvable=o["resolvable"],
                obligation=obligations[0]["kind"] if obligations else None,
                window=o["callbackWindow"]["when"],
            )
        )
    # repeats collapse to their earliest message: the rest hide behind it
    hidden = set()
    for r in day["repeats"].values():
        hidden.update(r["members"][1:])
    items = [i for i in items if i.id not in hidden]
    items.sort(key=lambda i: (-i.urgency, i.receivedAt, i.id))
    return items


@router.get("/messages/{mid}")
async def message(mid: str, request: Request, mode: int = 0) -> dict:
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    m = Message(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec, lang=v.lang,
                script=v.script, words=len(v.script.split()))
    if mode == 0:
        return m.model_dump()
    d = deps(request)
    bundle = await analyze(v, d)
    if mode == 2:
        section = await _message_mode2(v, bundle, MockCaseBackend(con(request)),
                                       Mode2Deps(d.con, d.store, d.provider, d.model))
        return {**m.model_dump(), "analysis": bundle, "mode2": section}
    return {**m.model_dump(), "analysis": bundle}


@router.post("/analysis/{mid}")
async def save_analysis(mid: str, request: Request, force: bool = False) -> dict:
    """Run (or re-run) the whole task set on one message and persist the bundle."""
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    return await analyze(v, deps(request), force=force)


class Correction(BaseModel):
    voicemail: str
    task: str
    field: str
    value: str | None
    provenance: str = "human"


@router.post("/corrections")
def record_correction(c: Correction, request: Request) -> dict:
    """A person edited an AI field: log the correction (the scoreboard scores it out).
    A correction value of `null` means "the human said there was no value"."""
    if next((v for v in voicemails(request) if v.id == c.voicemail), None) is None:
        raise HTTPException(404, f"no message {c.voicemail}")
    value_json = json.dumps(c.value, ensure_ascii=False) if c.value is not None else None
    con(request).execute(
        "INSERT INTO corrections (voicemail, task, field, value, provenance, at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (c.voicemail, c.task, c.field, value_json, c.provenance),
    )
    con(request).commit()
    return {"ok": True}


@router.get("/corrections")
def corrections(request: Request, voicemail: str | None = None) -> list[dict]:
    if voicemail:
        return [dict(r) for r in con(request).execute(
            "SELECT voicemail, task, field, value, provenance, at FROM corrections WHERE voicemail = ? ORDER BY id",
            (voicemail,))]
    return [dict(r) for r in con(request).execute(
        "SELECT voicemail, task, field, value, provenance, at FROM corrections ORDER BY id")]


@router.delete("/corrections")
def clear_corrections(request: Request) -> dict:
    con(request).execute("DELETE FROM corrections")
    con(request).commit()
    return {"cleared": True}


@router.get("/accuracy")
def accuracy(request: Request) -> dict:
    """How the AI is doing against the ground truth, corrected for human edits:
    per-task accuracy over the day's messages, plus the correction count."""
    d = deps(request)
    vms = voicemails(request)
    scores: dict[str, int] = {}
    n = len(vms)
    corrections_by: dict[str, dict[str, str | None]] = {}
    for r in d.con.execute("SELECT voicemail, task, field, value FROM corrections"):
        corrections_by.setdefault(r["voicemail"], {})[f"{r['task']}.{r['field']}"] = (
            json.loads(r["value"]) if r["value"] is not None else None
        )
    for v in vms:
        bundle = analyze_sync(v, d)
        truth = v.truth
        intent = bundle["intent_urgency"]["data"]
        ok = (intent["intent"] == truth.intent and intent["urgency"] == truth.urgency)
        scores["intent_urgency"] = scores.get("intent_urgency", 0) + ok
        route = bundle["routing"]["data"]
        scores["routing"] = scores.get("routing", 0) + (route["team"] == truth.team)
        out = bundle["extraction"]["data"]
        fields = {
            "caller": truth.callerName,
            "callbackNumber": truth.callbackNumber,
            "caseId": truth.caseId,
            "program": None,
            "requestedAction": None,
        }
        ok = True
        for f, true_val in fields.items():
            value = corrections_by.get(v.id, {}).get(f"extraction.{f}", _UNCORRECTED)
            if value is _UNCORRECTED:
                value = out[f]["value"]
            checked = f in ("caller", "callbackNumber", "caseId")
            if checked and value is not None and true_val is not None and value != true_val:
                ok = False
        scores["extraction"] = scores.get("extraction", 0) + ok
    acc = {k: round(v / n, 3) for k, v in scores.items()}
    total_corrections = d.con.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    return {"messages": n, **acc, "corrections": total_corrections}


@router.get("/lookup")
def lookup(q: str, request: Request) -> list[Case]:
    return MockCaseBackend(con(request)).search(q)[:20]


@router.get("/cases/{cid}")
def case(cid: str, request: Request) -> Case:
    c = MockCaseBackend(con(request)).case(cid)
    if not c:
        raise HTTPException(404, f"no case {cid}")
    return c


@router.get("/entries")
def entries(request: Request) -> dict[str, ManualEntry]:
    return {r["id"]: ManualEntry(**json.loads(r["entry"])) for r in con(request).execute("SELECT * FROM entries")}


@router.put("/entries/{mid}")
async def save_entry(mid: str, entry: ManualEntry, request: Request) -> ManualEntry:
    await message(mid, request, mode=0)
    c = con(request)
    c.execute("INSERT OR REPLACE INTO entries VALUES (?, ?)", (mid, entry.model_dump_json()))
    c.commit()
    return entry


@router.delete("/entries")
def clear_entries(request: Request) -> dict:
    c = con(request)
    c.execute("DELETE FROM entries")
    c.commit()
    return {"cleared": True}


@router.get("/assumptions")
def get_assumptions(request: Request) -> Assumptions:
    return request.app.state.assumptions


@router.put("/assumptions")
def put_assumptions(a: Assumptions, request: Request) -> Assumptions:
    request.app.state.assumptions = a
    return a


@router.get("/simulation")
def simulation(request: Request, mode: int = 0) -> Simulation:
    """One agent working the day. Mode 0: arrival order. Mode 1: the AI's urgency order (its own guesses, so
    its mistakes count). Mode 2: that order, and what the AI already answered only needs a person's approval:
    messages the case record resolves, callers in an incident (one holding reply), and a repeat caller's
    later messages (folded into the first)."""
    vms = voicemails(request)
    a, today = request.app.state.assumptions, request.app.state.today
    if mode == 0:
        return work_the_queue(vms, [v.id for v in vms], a, today)
    d = deps(request)
    urgency = {v.id: urgency_of(analyze_sync(v, d)) for v in vms}
    order = [v.id for v in sorted(vms, key=lambda v: (-urgency[v.id], v.receivedAt, v.id))]
    if mode == 1:
        return work_the_queue(vms, order, a, today)
    day, sections = mode2_day(request), mode2_messages(request)
    approve = {mid for mid, m2 in sections.items() if m2["resolution"]["resolvable"]}
    approve |= {mid for inc in day["incidents"] for mid in inc["members"]}
    approve |= {mid for r in day["repeats"].values() for mid in r["members"][1:]}
    return work_the_queue(vms, order, a, today, frozenset(approve))


@router.get("/incidents")
def incidents(request: Request) -> list[dict]:
    """The day's spike incidents: the alert time, the lead time and the card
    (the probable cause, the banner, the suggested actions)."""
    return mode2_day(request)["incidents"]


class ResolutionState(BaseModel):
    state: str  # approved | rejected
    reply: str | None = None  # what a human edits before sending, if anything


@router.get("/resolutions/{mid}")
def get_resolution(mid: str, request: Request) -> dict:
    """The mode-2 resolution of a message: the draft reply, the lookups the AI made,
    and the state a human has given it (draft | approved | rejected)."""
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    d = deps(request)
    bundle = analyze_sync(v, d)
    section = message_mode2(v, bundle, MockCaseBackend(con(request)),
                            Mode2Deps(d.con, d.store, d.provider, d.model))
    row = con(request).execute("SELECT state, reply, provenance, at FROM resolutions WHERE voicemail = ?", (mid,)).fetchone()
    state = dict(row) if row else {"state": "draft", "reply": None, "provenance": None, "at": None}
    return {"voicemail": mid, **state, **section}


@router.post("/resolutions/{mid}")
def set_resolution_state(mid: str, body: ResolutionState, request: Request) -> dict:
    """The one-click approve: the AI only drafts, a human approves before anything goes out.
    The state is persisted so the scoreboard can count the callbacks avoided."""
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    if body.state not in ("approved", "rejected"):
        raise HTTPException(400, f"state must be approved or rejected, got {body.state}")
    d = deps(request)
    bundle = analyze_sync(v, d)
    section = message_mode2(v, bundle, MockCaseBackend(con(request)),
                            Mode2Deps(d.con, d.store, d.provider, d.model))
    reply = body.reply if body.reply is not None else section["resolution"].get("reply")
    c = con(request)
    c.execute(
        "INSERT OR REPLACE INTO resolutions (voicemail, state, reply, provenance, at) "
        "VALUES (?, ?, ?, 'human', datetime('now'))",
        (mid, body.state, reply),
    )
    c.commit()
    request.app.state.mode2 = None  # the day's numbers change with the resolutions
    return {"ok": True, "state": body.state, "reply": reply}


@router.get("/scoreboard2")
def get_scoreboard2(request: Request) -> dict:
    """The mode-2 scoreboard: callbacks avoided, deadlines caught vs missed, the incident's lead time."""
    d = deps(request)
    vms = voicemails(request)
    bundles = {v.id: analyze_sync(v, d) for v in vms}
    return scoreboard2(vms, bundles, Mode2Deps(d.con, d.store, d.provider, d.model))


@router.get("/archive/root-causes")
def get_archive_root_causes(request: Request) -> dict:
    """Mode 3, view 1: the archive's cost by root cause (Pareto), at the configured labor rate."""
    from overheard.analytics.root_causes import root_causes

    return root_causes(con(request), request.app.state.settings.labor_rate)


@router.get("/archive/event-impact")
def get_archive_event_impact(request: Request) -> dict:
    """Mode 3, view 2: which moments (mailings, releases, policy changes) moved the call volume."""
    from overheard.analytics.events import event_impact

    return {"events": event_impact(con(request))}


@router.get("/archive/journeys")
def get_archive_journeys(request: Request) -> dict:
    """Mode 3, view 3: caller journeys — repeat callers, who is stuck in a loop, and where loops start."""
    from overheard.analytics.journeys import repeat_callers

    return repeat_callers(con(request))


@router.get("/archive/promises")
def get_archive_promises(request: Request) -> dict:
    """Mode 3, view 4: promises vs. outcomes — the centre's broken-promise rate by cause and team."""
    from overheard.analytics.promises import promise_outcomes

    return promise_outcomes(con(request))


@router.get("/archive/equity")
def get_archive_equity(request: Request) -> dict:
    """Mode 3, view 5: equity — wait times and outcomes by language and channel, and the gaps."""
    from overheard.analytics.equity import equity_report

    return equity_report(con(request))


class LetterDraft(BaseModel):
    text: str


@router.post("/archive/letter-lab")
def letter_lab(request: Request, draft: LetterDraft) -> dict:
    """Mode 3, view 6: the letter lab — pre-test a draft notice against the archive:
    which call-driver it sounds like, the predicted volume, the readers' questions, a rewrite."""
    from overheard.analytics.letter_lab import letter_lab as lab

    return lab(con(request), draft.text.strip())


class ArchiveQuestion(BaseModel):
    question: str


@router.post("/archive/ask")
def archive_ask(request: Request, q: ArchiveQuestion) -> dict:
    """Mode 3, view 7: ask the archive a plain-English question — answered over
    pre-computed contact totals, with real example messages cited as evidence."""
    from overheard.analytics.ask import ask

    return ask(con(request), q.question.strip())


@router.get("/knowledge-gaps")
def knowledge_gaps(request: Request) -> dict:
    """Mode 3, view 8: the questions the knowledge base doesn't answer, ranked
    by the archive's contact volume, with plain-code FAQ and IVR drafts."""
    from overheard.analytics.knowledge_gaps import knowledge_gaps as gaps

    return gaps(con(request))


@router.get("/weak-signals")
def weak_signals_route(request: Request) -> dict:
    """Mode 3, view 9: the weak signals the archive shows that could have
    caught each spike before it happened — trickle vs spike, how early."""
    from overheard.analytics.weak_signals import weak_signals

    cards = weak_signals(con(request))
    if cards:
        top = cards[0]
        trig = top["triggers"][0]["name"] if top["triggers"] else "no calendar event"
        trig_date = top["triggers"][0]["date"] if top["triggers"] else "nothing on the calendar"
        reason = top["driver"].replace("-", " ")
        headline = (
            f"The rush after {top['spikeEvent']['name']} ({top['spikeEvent']['date']}) was not sudden: "
            f"for {top['trickleWeeks']} weeks before it, '{reason}' calls ran high, up to "
            f"{top['multipleOfBaseline']} times their usual {top['baselinePerWeek']} a week. A simple alert "
            f"would have caught it about {top['monthsEarly']} months ({top['weeksEarly']} weeks) early. "
            f"The trickle started with {trig} ({trig_date}): {top['trickleTotal']} early calls, "
            f"then {top['spikeWeekContacts']} in the worst week."
        )
    else:
        headline = "No early warnings found: no reason for calling ran high in the weeks before a rush."
    return {"headline": headline, "signals": cards,
            "prov": "plain code · weekly totals over the archive"}


@router.get("/staffing-forecast")
def staffing_forecast_route(request: Request) -> dict:
    """Mode 3, view 10: the next 14 days of call volume and agent hours,
    projected from the archive's recent weekday average plus the events
    calendar's own decay curve."""
    from overheard.analytics.staffing import staffing_forecast

    r = staffing_forecast(con(request))
    if r["events"]:
        e = r["events"][0]
        headline = (
            f"Over the next {r['horizonDays']} days, {e['name']} ({e['date']}) is still bringing in calls "
            f"for {e['remainingDays']} more day{'s' if e['remainingDays'] != 1 else ''}: about "
            f"{e['projectedExcessContacts']} extra '{e['driver'].replace('-', ' ')}' calls "
            f"(~{e['projectedExcessAgentHours']} agent-hours). Otherwise expect a normal "
            f"~{r['weekdayBaseline']} calls a weekday, ~{r['totalProjectedAgentHours']} agent-hours in all."
        )
    else:
        headline = (
            f"No calendar events are active in the next {r['horizonDays']} days: "
            f"steady ~{r['weekdayBaseline']} contacts a weekday, "
            f"~{r['totalProjectedAgentHours']} agent-hours across the window."
        )
    return {"headline": headline, **r,
            "prov": "plain code · trailing 90-weekday baseline + events-calendar decay"}
