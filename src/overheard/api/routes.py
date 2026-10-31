"""The REST API: the day's queue, a message, case lookups, manual entries, the simulation, the assumptions."""

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from overheard.adapters.backend.mock import MockCaseBackend
from overheard.data.models import Case, Voicemail
from overheard.pipeline.simulate import Assumptions, Simulation, work_the_queue

router = APIRouter(prefix="/api")


def con(request: Request) -> sqlite3.Connection:
    return request.app.state.db


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
def queue(request: Request) -> list[QueueItem]:
    """Mode 0's inbox: when, who, how long; no content until it's played."""
    worked = {r[0] for r in con(request).execute("SELECT id FROM entries")}
    return [QueueItem(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec,
                      worked=v.id in worked) for v in voicemails(request)]


@router.get("/messages/{mid}")
def message(mid: str, request: Request) -> Message:
    v = next((v for v in voicemails(request) if v.id == mid), None)
    if not v:
        raise HTTPException(404, f"no message {mid}")
    return Message(id=v.id, receivedAt=v.receivedAt, callerId=v.callerId, durationSec=v.durationSec, lang=v.lang,
                   script=v.script, words=len(v.script.split()))


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
def save_entry(mid: str, entry: ManualEntry, request: Request) -> ManualEntry:
    message(mid, request)
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
