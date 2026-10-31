"""Mode 2 · the day computed up front: the queue's groups, the per-message
mode-2 section (resolution, obligations, missing info, repeat link, callback
window), the incident list and the mode-2 scoreboard.

Everything here is the same code the tests and the front end read, so what the
screen shows is what the tests check. The LLM parts (incident card, resolution
decision) carry their own provenance; the numbers (clusters, deadlines,
metrics) are plain code.
"""

import sqlite3

from overheard.data.models import Voicemail
from overheard.llm import ResponseStore
from overheard.llm.provider import LLMProvider
from overheard.pipeline.flags import deadline_at, obligations_of
from overheard.pipeline.groups import group_day, link_repeats, missing_info
from overheard.pipeline.incidents import IncidentDeps, incidents_in_clusters
from overheard.pipeline.resolution import ResolutionDeps, brief_context, resolve


class Mode2Deps:
    """Everything a mode-2 computation needs (the API builds it from the app state)."""

    def __init__(self, con: sqlite3.Connection, store: ResponseStore, provider: LLMProvider, model: str):
        self.con = con
        self.store = store
        self.provider = provider
        self.model = model

    def incidents(self) -> IncidentDeps:
        return IncidentDeps(store=self.store, provider=self.provider, model=self.model)

    def resolution(self) -> ResolutionDeps:
        return ResolutionDeps(con=self.con, store=self.store, provider=self.provider, model=self.model)


def message_mode2(v: Voicemail, bundle: dict, backend, deps: Mode2Deps) -> dict:
    """The mode-2 section of one message: the resolution decision (with the
    lookups it made), the obligation flags with their deadline clocks, the
    missing-info recovery, and the callback window."""
    import asyncio

    return asyncio.run(_message_mode2(v, bundle, backend, deps))


async def _message_mode2(v: Voicemail, bundle: dict, backend, deps: Mode2Deps) -> dict:
    resolution = (await resolve(v, {v.id: bundle}, backend, deps.resolution()))["resolution"]
    case = resolution["caseId"] and backend.case(resolution["caseId"])
    obligations = []
    for o in obligations_of(v.script, (bundle.get("intent_urgency", {}).get("data") or {}).get("obligations", [])):
        obligations.append({**o, "due": deadline_at(v.receivedAt, o["kind"])})
    missing = missing_info([v], {v.id: bundle}, backend).get(v.id)
    return {
        "resolution": resolution,
        "brief": brief_context(v, case, {v.id: bundle}),
        "obligations": obligations,
        "missingInfo": missing,
    }


def day_bundles(vms: list[Voicemail], bundles: dict[str, dict], backend, deps: Mode2Deps) -> dict:
    """The queue-level reasoning over the whole day: the similarity clusters,
    the repeat-caller collapses, the missing-info recoveries and the incidents."""
    clusters = group_day(vms, bundles)
    by_member = {k: [v for v in vms if v.id in members] for k, members in clusters.items()}
    return {
        "clusters": clusters,
        "repeats": link_repeats(vms, bundles),
        "missingInfo": missing_info(vms, bundles, backend),
        "incidents": incidents_in_clusters(by_member, deps.incidents()),
    }


def _obligations_detected(v: Voicemail, bundle: dict) -> set[str]:
    data = (bundle.get("intent_urgency", {}).get("data") or {}).get("obligations", [])
    return {o["kind"] for o in obligations_of(v.script, data)}


def scoreboard2(vms: list[Voicemail], bundles: dict[str, dict], deps: Mode2Deps) -> dict:
    """The mode-2 scoreboard: callbacks avoided, deadlines caught vs missed, and
    the incident's lead time — against the day's ground truth."""
    con = deps.con
    approved = [r[0] for r in con.execute("SELECT voicemail FROM resolutions WHERE state = 'approved'")]
    approved_set = set(approved)
    resolvable = [v.id for v in vms if v.truth.resolvableBy]
    closed = [i for i in approved_set if i in set(resolvable)]
    caught, missed, extra = [], [], []
    clocks = []
    for v in vms:
        detected = _obligations_detected(v, bundles.get(v.id, {}))
        truth = detected & set(v.truth.obligations)
        extra_kinds = detected - set(v.truth.obligations)
        for kind in sorted(truth):
            caught.append({"id": v.id, "kind": kind})
        for kind in sorted(extra_kinds):
            extra.append({"id": v.id, "kind": kind})
        for kind in sorted(set(v.truth.obligations) - detected):
            missed.append({"id": v.id, "kind": kind})
        for kind in sorted(detected):
            clocks.append({"id": v.id, "kind": kind, "due": deadline_at(v.receivedAt, kind),
                           "grounded": kind in truth})
    incidents = incidents_in_clusters(
        {k: [v for v in vms if v.id in members] for k, members in group_day(vms, bundles).items()},
        deps.incidents(),
    )
    incident = incidents[0] if incidents else None
    return {
        "callbacksAvoided": {
            "approved": len(approved),
            "resolvable": len(resolvable),
            "closedWithNoCall": len(closed),
            "share": round(len(closed) / len(resolvable), 3) if resolvable else 0.0,
        },
        "deadlines": {"caught": len(caught), "missed": len(missed), "extraFlags": len(extra),
                      "caughtItems": caught, "missedItems": missed, "extraItems": extra, "clocks": clocks},
        "incident": {"alertAt": incident["alertAt"], "leadMin": incident["leadMin"],
                     "title": incident["card"]["title"]} if incident else None,
    }
