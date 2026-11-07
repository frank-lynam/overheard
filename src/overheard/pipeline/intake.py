"""What happens to a voicemail as it comes in, stage by stage, in order. Each stage can end processing for it.

  [A] trigger scan: plain code, the moment the transcript exists; a hit raises an alert at once
  later stages (the junk filter, the problem check, ...) run after it, never before

The log records the order things happened in, so tests can check that an alert is raised before any later
stage starts (ordering, not speed)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from overheard.data.models import Voicemail
from overheard.triggers import TriggerHit, TriggerList, default_list


@dataclass
class Intake:
    voicemail: Voicemail
    hits: list[TriggerHit] = field(default_factory=list)
    alert: dict | None = None
    log: list[str] = field(default_factory=list)      # "transcript", "alert", "<stage> start", ...
    alert_ms: float | None = None                      # transcript to alert, on the text path


Stage = tuple[str, Callable[[Intake], None]]


def alert_for(vm: Voicemail, hits: list[TriggerHit], triggers: TriggerList) -> dict | None:
    """The alert a voicemail raises: its most urgent category, every hit, and (safety) who it would page."""
    if not hits:
        return None
    top = min(hits, key=lambda h: h.priority)
    page = triggers.page_for(top.category)
    return {"id": vm.id, "receivedAt": vm.receivedAt, "category": top.category,
            "label": triggers.categories[top.category]["label"], "priority": top.priority,
            "safety": top.category == "safety", "hits": [h.as_dict() for h in hits],
            "page": f"would page: {page} (simulated)" if page else None}


def intake(vm: Voicemail, later: list[Stage] = (), triggers: TriggerList | None = None) -> Intake:
    triggers = triggers or default_list()
    it = Intake(vm)
    it.log.append("transcript")
    started = time.perf_counter()
    it.hits = triggers.scan(vm.script)
    it.alert = alert_for(vm, it.hits, triggers)
    if it.alert:
        it.alert_ms = round((time.perf_counter() - started) * 1000, 2)
        it.log.append("alert")
    for name, run in later:
        it.log.append(f"{name} start")
        run(it)
    return it
