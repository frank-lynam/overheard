"""Resolution without a callback: decide which backend lookups answer the
message, draft the reply the caller would get, and (for the calls that must
still happen) the pre-researched callback brief.

The LLM does the language judgment — what the caller is actually asking,
whether the answer is safe to send without a human, and what to say. The
lookups themselves (case status, payment schedule, documents received) are
plain code in `pipeline/resolution.py`, called with the ids the pipeline
already has; their *results* are what the task carries. The ground-truth
labels travel in `Task.context` only (the mock and the scorers use them; a
live host never sees them).
"""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Case, Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register

LOOKUPS = ["case_status", "payment_schedule", "documents_received"]


class ResolutionOut(BaseModel):
    resolvable: bool  # can this be answered from the case record alone?
    lookups: list[Literal["case_status", "payment_schedule", "documents_received"]]  # the tool calls it would make
    answer: str  # the answer, in plain words, grounded in what the lookups show
    reply: str  # the text reply the caller would get (approved before sending)
    brief: str  # for the call that still needs making: case history, prior contacts, likely answer
    beliefMismatch: str | None  # where the caller's understanding and the record disagree


@_register
class resolution:
    name = "resolution"

    @classmethod
    def build(cls, v: Voicemail, case: Case | None = None, extra: str = "") -> Task:
        facts = json.dumps(case.model_dump(mode="json"), ensure_ascii=False) if case else "no case on file"
        return Task(
            name=cls.name,
            description="Decide which lookups answer the message; draft the reply or the callback brief.",
            system=("You work a benefits-service voicemail against the case system. "
                    "The lookups (case_status, payment_schedule, documents_received) have already been made "
                    "for you; their results are the case record below. If the record answers the caller's "
                    "question, set resolvable true and draft the text reply the caller would get: short, in "
                    "plain words, stating the actual answer, no promises beyond the record. If a person still "
                    "has to call, set resolvable false and write the pre-researched callback brief instead: "
                    "case history, prior contacts, what was promised, and the likely answer, so the agent "
                    "dials already knowing it. If the caller believes something the record contradicts (a "
                    "missed payment that is actually scheduled, a form already received), say so in "
                    "beliefMismatch; otherwise null. "
                    "Reply with only a JSON object: "
                    + json.dumps(
                        {"resolvable": "boolean",
                         "lookups": "array of any of " + json.dumps(LOOKUPS),
                         "answer": "string", "reply": "string", "brief": "string",
                         "beliefMismatch": "string or null"}
                    )),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  f"Case record from the lookups:\n{facts}\n"
                  + (f"{extra}\n" if extra else "")
                  + "\nDecide and draft."),
            output_model=ResolutionOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nWhere's my payment? It's always on the "
                                           "third and nothing has come. My case is 1 3 3 7 0 2.\n\n"
                                            "Case record from the lookups:\n"
                                            '{"id": "FBS-133702", "name": "Frank Delgado", "status": "active", '
                                            '"payments": [{"amount": 977.0, "date": "2026-03-12", "status": '
                                            '"scheduled"}], "docs": [], "lastAction": "2026-02-27 payment date '
                                            'moved to the 12th"}\n\nDecide and draft.'},
                {"role": "assistant",
                 "content": '{"resolvable": true, "lookups": ["payment_schedule", "case_status"], '
                             '"answer": "The payment was not missed: the date was moved to the 12th.", '
                             '"reply": "Hi, your March payment of $977.00 is on file and scheduled for '
                             '2026-03-12. No action is needed from you.", '
                             '"brief": "Caller expects payment on the 3rd; the record shows the date was moved '
                             'to the 12th on 2026-02-27. Safe to answer in writing.", "beliefMismatch": '
                             '"thinks the payment was missed; it is scheduled for 2026-03-12"}'},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
