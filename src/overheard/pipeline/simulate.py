"""'Work the queue': one agent working the day's voicemail in a given order, from the start of the shift.
Pure arithmetic over the assumptions, so every number on the scoreboard can be traced and adjusted."""

from datetime import datetime, timedelta

from pydantic import BaseModel

from overheard.data.models import Voicemail


class Assumptions(BaseModel):
    handleMin: float = 3.5          # handling time per message, after listening
    callbackMin: float = 6.0        # a callback, when the message needs one
    listenSpeed: float = 1.0        # 1.0 = listening at the speed it was spoken
    shiftStart: str = "08:00"
    shiftEnd: str = "16:30"
    lunch: str = "12:00"
    lunchMin: int = 30
    rate: float = 75.0              # fully loaded dollars per agent-hour
    workingDays: int = 250
    urgentWithinMin: int = 120      # welfare and urgent hardship: a person reaches it within this
    approveMin: float = 1.0         # mode 2: a person reads the AI's drafted answer and approves it (no callback)


NO_CALLBACK = {"no-content", "compliment"}
SAME_DAY = {"congressional", "legal", "records"}


class Touch(BaseModel):
    id: str
    firstTouch: str | None          # "HH:MM", or None if not reached by the end of the shift
    minutes: float
    callback: bool


class Simulation(BaseModel):
    order: list[str]
    touches: list[Touch]
    agentHours: float
    reachedBy: str | None           # when the last message was finished, if within the shift
    unreached: int
    urgentId: str | None
    urgentFirstTouch: str | None
    urgentWaitMin: float | None
    obligationsCaught: int
    obligationsMissed: int
    missed: list[str]
    dollarsPerDay: float


def _at(day: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}")


def work_the_queue(vms: list[Voicemail], order: list[str], a: Assumptions, day: str,
                   approve: frozenset[str] = frozenset()) -> Simulation:
    """One agent from the shift start, always taking the first message in `order` that has arrived (arrival
    order for mode 0; the AI's urgency for modes 1 and 2). Messages in `approve` only need a person to approve
    the AI's answer (`approveMin`): no listening, no handling, no callback."""
    by_id = {v.id: v for v in vms}
    clock, end = _at(day, a.shiftStart), _at(day, a.shiftEnd)
    lunch, lunch_done = _at(day, a.lunch), False
    touches, total, last = [], 0.0, None
    waiting = list(order)
    while waiting:
        arrived_now = [m for m in waiting if datetime.fromisoformat(by_id[m].receivedAt) <= clock]
        mid = arrived_now[0] if arrived_now else min(waiting, key=lambda m: by_id[m].receivedAt)
        waiting.remove(mid)
        v = by_id[mid]
        if mid in approve:
            callback, minutes = False, a.approveMin
        else:
            callback = v.truth.rootCause not in NO_CALLBACK
            minutes = v.durationSec / 60 / a.listenSpeed + a.handleMin + (a.callbackMin if callback else 0.0)
        total += minutes
        arrived = datetime.fromisoformat(v.receivedAt)
        clock = max(clock, arrived)
        if not lunch_done and clock >= lunch:
            clock, lunch_done = clock + timedelta(minutes=a.lunchMin), True
        if clock >= end:
            touches.append(Touch(id=mid, firstTouch=None, minutes=round(minutes, 1), callback=callback))
            continue
        touches.append(Touch(id=mid, firstTouch=clock.strftime("%H:%M"), minutes=round(minutes, 1), callback=callback))
        clock += timedelta(minutes=minutes)
        last = clock
    first = {t.id: t.firstTouch for t in touches}
    urgent = next((v for v in vms if v.truth.urgency == 5 and v.truth.intent == "urgent_hardship"), None)
    wait = None
    if urgent and first.get(urgent.id):
        wait = (_at(day, first[urgent.id]) - datetime.fromisoformat(urgent.receivedAt)).total_seconds() / 60
    caught, missed = 0, []
    for v in vms:
        for o in v.truth.obligations:
            ft = first.get(v.id)
            if o == "welfare":
                ok = ft is not None and (_at(day, ft) - datetime.fromisoformat(v.receivedAt)).total_seconds() / 60 \
                    <= a.urgentWithinMin
            else:
                ok = ft is not None
            caught += ok
            if not ok:
                missed.append(f"{v.id}:{o}")
    return Simulation(
        order=[t.id for t in touches], touches=touches, agentHours=round(total / 60, 2),
        reachedBy=last.strftime("%H:%M") if last and all(t.firstTouch for t in touches) else None,
        unreached=sum(t.firstTouch is None for t in touches), urgentId=urgent.id if urgent else None,
        urgentFirstTouch=first.get(urgent.id) if urgent else None, urgentWaitMin=round(wait) if wait is not None else None,
        obligationsCaught=caught, obligationsMissed=len(missed), missed=missed,
        dollarsPerDay=round(total / 60 * a.rate, 2))
