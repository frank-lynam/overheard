"""The REST API: the day's queue, a message, case lookups, manual entries, the simulation, the assumptions."""

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from overheard.adapters.backend.mock import MockCaseBackend
from overheard.data.models import Case, Voicemail
from overheard.pipeline.analyze import AnalysisDeps, analyze, analyze_sync, team_of, urgency_of
from overheard.pipeline.simulate import Assumptions, Simulation, work_the_queue

router = APIRouter(prefix="/api")

#: marks a field nobody corrected, so a correction to `null` is not confused with no correction
_UNCORRECTED = object()


def con(request: Request) -> sqlite3.Connection:
    return request.app.state.db


def deps(request: Request) -> AnalysisDeps:
    # The db connection is shared by every thread (sync routes run in worker threads),
    # so the analysis is serialized on a per-app lock; bundles are cached per message.
    return AnalysisDeps(
        con=con(request),
        lock=request.app.state.analyze_lock,
        cache=request.app.state.analysis_cache,
        store=request.app.state.store,
        provider=request.app.state.provider,
        model=request.app.state.settings.llm_model or "mock",
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
def queue(request: Request, mode: int = 0) -> list[QueueItem] | list[Mode1Item]:
    """Mode 0's inbox: when, who, how long; no content until it's played.
    Mode 1: the same inbox ordered by the AI's urgency, with the routed team."""
    if mode == 0:
        worked = {r[0] for r in con(request).execute("SELECT id FROM entries")}
        return [QueueItem(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                          worked=v.id in worked) for v in voicemails(request)]
    d = deps(request)
    worked = {r[0] for r in d.con.execute("SELECT id FROM entries")}
    items = []
    for v in voicemails(request):
        bundle = analyze_sync(v, d)
        items.append(
            Mode1Item(
                id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                worked=v.id in worked, urgency=urgency_of(bundle), team=team_of(bundle),
            )
        )
    items.sort(key=lambda i: (-i.urgency, i.receivedAt, i.id))
    return items


@router.get("/messages/{mid}")
async def message(mid: str, request: Request, mode: int = 0) -> dict:
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    m = Message(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec, lang=v.lang,
                script=v.script, words=len(v.script.split()))
    if mode != 0:
        bundle = await analyze(v, deps(request))
        return {**m.model_dump(), "analysis": bundle}
    return m.model_dump()


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
    """Mode 0: one agent, the queue in arrival order. (Later modes change the order and the work.)"""
    vms = voicemails(request)
    order = [v.id for v in vms]
    return work_the_queue(vms, order, request.app.state.assumptions, request.app.state.today)
