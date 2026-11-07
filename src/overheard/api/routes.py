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
    alert: dict | None = None   # a trigger alert (from Mode 1 on): category, label, priority, safety


def run_coro(coro):
    """Run a coroutine to its end from sync code, also from inside an async route (then in a thread of its own)."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()


def intakes(request: Request) -> dict:
    """Each of the day's voicemails as it came in: [A] the trigger scan, [B] the junk filter, once."""
    if request.app.state.intakes is None:
        from overheard.llm.run import run_task
        from overheard.llm.tasks import TASKS
        from overheard.pipeline.intake import intake
        from overheard.pipeline.junk import JunkRules, callers_per_script, decide
        vms, d = voicemails(request), deps(request)
        rules, per_script = JunkRules.load(), callers_per_script(vms)

        def classify(v):
            r = run_coro(run_task(d.provider, TASKS["junk_classify"].build(v), d.model, d.store, write=d.write))
            return r.data.verdict, r.data.reason, r.provenance

        def junk_stage(it):
            it.junk = decide(it.voicemail, bool(it.alert and it.alert["safety"]), rules, per_script, classify)
        request.app.state.intakes = {v.id: intake(v, later=[("junk filter", junk_stage)]) for v in vms}
    return request.app.state.intakes


def filtered_ids(request: Request) -> set[str]:
    """Voicemails the junk filter kept out of the queue (from Mode 1 on), less any a person reopened."""
    reopened = {r[0] for r in con(request).execute("SELECT item_id FROM junk_reopened")}
    return {i for i, it in intakes(request).items() if it.junk and it.junk["disposition"] == "filtered"} - reopened


def queued(request: Request) -> list[Voicemail]:
    """The voicemails that reach a person from Mode 1 on: everything but filtered junk."""
    out = filtered_ids(request)
    return [v for v in voicemails(request) if v.id not in out]


def alert_of(request: Request, mid: str) -> dict | None:
    a = intakes(request)[mid].alert
    return {k: a[k] for k in ("category", "label", "priority", "safety")} if a else None


def alert_first(item) -> tuple:
    """Alerted voicemails go in front of a person at once (safety first), then the AI's urgency."""
    return (item.alert["priority"] if item.alert else 9, -item.urgency, item.receivedAt, item.id)


class Mode2Item(QueueItem):
    urgency: int
    alert: dict | None = None
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
            vms = queued(request)
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
                v.id: message_mode2(v, analyze_sync(v, d), backend, mdeps) for v in queued(request)
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
    vms = queued(request)                       # junk the filter kept out doesn't reach a person
    bundles = {v.id: analyze_sync(v, d) for v in vms}
    if mode == 1:
        worked = {r[0] for r in d.con.execute("SELECT id FROM entries")}
        items = [
            Mode1Item(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                      worked=v.id in worked, urgency=urgency_of(bundles[v.id]), team=team_of(bundles[v.id]),
                      alert=alert_of(request, v.id))
            for v in vms
        ]
        items.sort(key=alert_first)
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
                alert=alert_of(request, v.id), clusterSize=cluster_of.get(v.id, 1),
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
    items.sort(key=alert_first)
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
    alert = intakes(request)[v.id].alert       # the trigger scan's hits, highlighted in the transcript
    if mode == 2:
        section = await _message_mode2(v, bundle, MockCaseBackend(con(request)),
                                       Mode2Deps(d.con, d.store, d.provider, d.model))
        return {**m.model_dump(), "analysis": bundle, "mode2": section, "alert": alert}
    return {**m.model_dump(), "analysis": bundle, "alert": alert}


class JunkItem(BaseModel):
    id: str
    receivedAt: str
    callerId: str
    durationSec: int
    script: str
    reason: str
    decidedBy: str              # rule:<id> | llm | fallback


class RetroDefinition(BaseModel):
    description: str
    examples: list[str] = []
    since: str
    until: str
    team: str | None = None
    origin: str = "analyst"


def retro_suggestion(request: Request) -> dict | None:
    """A problem definition offered from today's spike, or None on a day with no spike."""
    from overheard.pipeline.retro import suggest
    incidents = mode2_day(request)["incidents"]
    if not incidents:
        return None
    by = {v.id: v for v in voicemails(request)}
    inc = incidents[0]
    return suggest(inc, [by[m] for m in inc["members"] if m in by], request.app.state.today)


@router.get("/retro")
def retro_suggest(request: Request) -> dict:
    """Mode 3's "Overlooked before today": the definition offered from today's spike (the analyst can change it)."""
    return {"suggested": retro_suggestion(request)}


@router.post("/retro")
def retro(request: Request, body: RetroDefinition | None = None) -> dict:
    """Search the archive for past contacts that were this problem but were overlooked. With no body, the definition
    offered from today's spike. On demand only; each definition is searched once."""
    from overheard.llm.run import run_task
    from overheard.pipeline.retro import search
    d = body.model_dump() if body else retro_suggestion(request)
    if d is None:
        raise HTTPException(400, "no spike today to start from: give a definition")
    key = json.dumps(d, sort_keys=True)
    cache = request.app.state.retro
    if key not in cache:
        dp = deps(request)
        cache[key] = search(con(request), d, lambda task: run_coro(run_task(dp.provider, task, dp.model, dp.store,
                                                                            write=dp.write)))
    return cache[key]


@router.get("/junk")
def junk(request: Request) -> dict:
    """What the junk filter kept out of the queue today (from Mode 1 on), each with why and what decided it, and the
    counts: how many it caught, how many real calls it filtered (the false-junk rate) and how many it left to a person
    as unsure."""
    out_ids, ins = filtered_ids(request), intakes(request)
    vms = {v.id: v for v in voicemails(request)}
    items = [JunkItem(id=i, receivedAt=vms[i].receivedAt, callerId=vms[i].callerId, durationSec=vms[i].durationSec,
                      script=vms[i].script, reason=ins[i].junk["reason"], decidedBy=ins[i].junk["decidedBy"])
             for i in sorted(out_ids, key=lambda i: (vms[i].receivedAt, i))]
    real = [v for v in vms.values() if not v.truth.junk]
    junk_ = [v for v in vms.values() if v.truth.junk]
    false = sum(v.id in out_ids for v in real)
    return {"filtered": [i.model_dump() for i in items],
            "counts": {"calls": len(vms), "junk": len(junk_), "caught": sum(v.id in out_ids for v in junk_),
                       "realFiltered": false, "falseJunkRate": round(false / len(real), 3) if real else 0.0,
                       "unsure": sum(1 for it in ins.values() if it.junk and it.junk["verdict"] == "unsure"),
                       "listenMinSaved": round(sum(vms[i].durationSec for i in out_ids) / 60, 1)}}


@router.post("/junk/{mid}/reopen")
def reopen_junk(mid: str, request: Request) -> dict:
    """A person puts a filtered voicemail back in the queue."""
    if mid not in filtered_ids(request):
        raise HTTPException(404, f"{mid} isn't filtered")
    c = con(request)
    c.execute("INSERT OR IGNORE INTO junk_reopened (item_id, at) VALUES (?, datetime('now'))", (mid,))
    c.commit()
    with request.app.state.mode2_lock:            # the day's later work includes it now
        request.app.state.mode2 = request.app.state.mode2_messages = None
    return {"reopened": mid}


def desk(request: Request):
    """The ticket desk (pipeline/tickets.py): problem check, team proposal from memory, the workflow sink."""
    st = request.app.state
    if st.desk is None:
        from overheard.llm.run import run_task
        from overheard.pipeline.tickets import Desk
        from overheard.workflow.sink import HearthboardSink, MockWorkflowSink
        s, d = st.settings, deps(request)
        if s.workflow_url:
            token = s.workflow_token.get_secret_value() if s.workflow_token else ""
            factory = lambda _con: HearthboardSink(s.workflow_url, token)   # noqa: E731
        else:
            factory = MockWorkflowSink
        st.desk = Desk(s.db_path, st.today, factory,
                       lambda task: run_coro(run_task(d.provider, task, d.model, d.store, write=d.write)))
    return st.desk


@router.get("/tickets")
def tickets(request: Request) -> dict:
    """Mode 2 on: the tickets filed so far (decisions read back first), the day's progress through them, and how
    well routing memory proposes teams on routings it hasn't seen."""
    dk = desk(request)
    dk.refresh()
    units = dk.units(queued(request), mode2_day(request))
    done = dk.done_units()
    rows = dk.con.execute("SELECT is_problem, COUNT(*) FROM ticket_units GROUP BY is_problem").fetchall()
    by = {r[0]: r[1] for r in rows}
    ts = dk.tickets()
    from overheard.memory.store import teams_map
    return {"tickets": ts, "sink": dk.sink.name, "teams": teams_map()["teams"], "accuracy": dk.accuracy(),
            "counts": {"revealed": len(done), "toReveal": sum(u["unit_id"] not in done for u in units),
                       "problems": by.get(1, 0), "notProblems": by.get(0, 0),
                       **{st: sum(t["status"] == st for t in ts) for st in ("proposed", "accepted", "moved", "declined")}}}


class Reveal(BaseModel):
    all: bool = False


@router.post("/tickets/reveal")
def reveal_tickets(body: Reveal, request: Request) -> dict:
    """Reveal the day's voicemails in arrival order until the next one makes a ticket (or all of them): each team
    proposal is worked out now, from the memory as it stands."""
    dk = desk(request)
    dk.refresh()
    vms = queued(request)
    alerts = {i: it.alert for i, it in intakes(request).items() if it.alert}
    made = dk.reveal(dk.units(vms, mode2_day(request)), {v.id: v for v in vms}, alerts, body.all)
    return {"made": made}


@router.get("/tickets/{tid}")
def get_ticket(tid: str, request: Request) -> dict:
    t = desk(request).ticket(tid)
    if not t:
        raise HTTPException(404, f"no ticket {tid}")
    return t


class Decision(BaseModel):
    action: str                 # accept | move | decline
    team: str | None = None     # for a move
    by: str = "supervisor"


@router.post("/tickets/{tid}/decide")
def decide_ticket(tid: str, body: Decision, request: Request) -> dict:
    """The mock board's buttons (with hearthboard, people decide there): accept, move or decline."""
    dk = desk(request)
    if dk.sink.name != "mock":
        raise HTTPException(400, "tickets are decided in the workflow system; this console only reads the decision back")
    t = dk.ticket(tid)
    if not t:
        raise HTTPException(404, f"no ticket {tid}")
    from overheard.memory.store import teams_map
    if body.action == "move" and body.team not in {*teams_map()["teams"], teams_map()["general"]}:
        raise HTTPException(400, "move it to one of the teams")
    try:
        dk.sink.decide(t["board_id"], body.action, body.team, body.by)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    dk.refresh()
    return dk.ticket(tid)


@router.get("/alerts")
def alerts(request: Request, mode: int = 1) -> dict:
    """Trigger alerts (from Mode 1 on): the voicemails with code words, most urgent first, each with its hits,
    who it would page (safety, simulated) and how long the alert took from the transcript (the text path)."""
    from overheard.triggers import default_list
    tl = default_list()
    found = [] if mode == 0 else sorted(
        ({**it.alert, "alertMs": it.alert_ms} for it in intakes(request).values() if it.alert),
        key=lambda a: (a["priority"], a["receivedAt"]))
    return {"alerts": found, "illustrative": tl.illustrative, "note": tl.note}


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
    vms = queued(request)
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
    if mode == 0:                               # everything, junk included: someone listens to all of it
        return work_the_queue(vms, [v.id for v in vms], a, today)
    vms = queued(request)                       # from Mode 1: the junk filter keeps the rest out
    d = deps(request)
    urgency = {v.id: urgency_of(analyze_sync(v, d)) for v in vms}
    rank = {v.id: (intakes(request)[v.id].alert or {}).get("priority", 9) for v in vms}   # alerts first
    order = [v.id for v in sorted(vms, key=lambda v: (rank[v.id], -urgency[v.id], v.receivedAt, v.id))]
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
    vms = queued(request)
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
