"""Mode 2 · the incident: when a similarity cluster spikes, the LLM names it and
drafts the card (banner, probable cause, actions). The numbers — first seen,
count, lead time — come from the spike test in groups.py; the language is the
`incident` task's job, so the card carries its own provenance."""

from overheard.data.models import Voicemail
from overheard.llm import ResponseStore, run_task
from overheard.llm.provider import LLMProvider
from overheard.llm.tasks.incident import incident
from overheard.pipeline.groups import spike_in_cluster


class IncidentDeps:
    def __init__(self, store: ResponseStore, provider: LLMProvider, model: str):
        self.store = store
        self.provider = provider
        self.model = model


async def incident_card(member_msgs: list[Voicemail], deps: IncidentDeps,
                        window_min: int = 30, count: int = 6) -> dict | None:
    """The spike test on one cluster, and — if it fires — the incident card for it.
    `count`/`window_min`: the agency's spike threshold (6 similar messages in a
    rolling 30 minutes, on the seeded day)."""
    spike = spike_in_cluster(member_msgs, window_min=window_min, count=count)
    if spike is None:
        return None
    msgs = sorted(member_msgs, key=lambda v: v.receivedAt)
    result = await run_task(
        deps.provider, incident.build([m.script for m in msgs[:6]], spike["firstAt"], spike["count"]),
        deps.model, deps.store, write=False,
    )
    card = result.data.model_dump(mode="json")
    return {
        "firstAt": spike["firstAt"],
        "alertAt": spike["alertAt"],
        "leadMin": spike["leadMin"],
        "count": spike["count"],
        "size": spike["size"],
        "members": [m.id for m in msgs],
        "card": {**card, "provenance": result.provenance, "model": result.model},
    }


def incidents_in_clusters(clusters: dict[str, list[Voicemail]], deps: IncidentDeps,
                          window_min: int = 30, count: int = 6) -> list[dict]:
    """Sync driver over the day's clusters (the big one first), for the API and the tests."""
    import asyncio

    async def _all():
        out = []
        for members in sorted(clusters.values(), key=len, reverse=True):
            if len(members) >= 3:
                inc = await incident_card(members, deps, window_min=window_min, count=count)
                if inc:
                    out.append(inc)
        return out

    return asyncio.run(_all())
