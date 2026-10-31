"""Name a spike cluster and draft the incident card: probable cause and the
actions to take. The numbers (first seen, count, lead time) come from the
spike test in pipeline/groups.py; the language is the LLM's job."""

import json

from pydantic import BaseModel

from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class IncidentOut(BaseModel):
    title: str  # the short name the banner shows
    probableCause: str  # one sentence
    banner: str  # the one line the IVR/queue banner says
    actions: list[str]  # suggested actions, in order: e.g. banner, portal ticket, holding reply


@_register
class incident:
    name = "incident"

    @classmethod
    def build(cls, messages: list[str], first_at: str, count: int) -> Task:
        samples = "\n---\n".join(messages[:6])
        return Task(
            name=cls.name,
            description="Name a spike of similar messages and draft the incident card.",
            system=("You work the benefits-service call center. A burst of similar voicemails has "
                    "just been detected. Reply with only a JSON object: "
                    "{\"title\": string, \"probableCause\": string, \"banner\": string, "
                    "\"actions\": array of strings}. title names the problem in a few words. "
                    "probableCause is one sentence: the most likely cause, from the callers' own words. "
                    "banner is the one line shown to new callers until it's fixed. "
                    "actions lists the suggested actions in order (an IVR banner, a ticket for the "
                    "responsible team, a holding reply for affected callers)."),
            user=(f"A cluster of {count} similar messages was first seen at {first_at}. "
                  "Sample of what the callers said:\n---\n" + samples + "\n\nName it and draft the card."),
            output_model=IncidentOut,
            examples=[
                {"role": "user",
                 "content": "A cluster of 9 similar messages was first seen at 2026-03-10T09:08:11. "
                             "Sample: I get error 4012 when I sign in to the portal."},
                {"role": "assistant",
                 "content": json.dumps(
                     {"title": "Portal sign-in failure (error 4012)",
                      "probableCause": "A portal deployment this morning broke the sign-in page "
                                       "with error 4012, and callers are phoning instead.",
                      "banner": "Portal sign-in is down. We are aware of it; no need to call again.",
                      "actions": ["Show the banner to new callers immediately",
                                  "Open a P1 ticket for the portal team",
                                  "Send the holding reply to every caller in the cluster"]})},
            ],
            context=json.dumps({"first_at": first_at, "count": count, "samples": messages[:6]}, ensure_ascii=False),
        )
