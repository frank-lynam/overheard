"""Stage [C]: is this voicemail a real problem a team has to act on (a held payment, a broken sign-in, a records
request), or something answered on the call (a status question, thanks)? Names the kind of problem and says it in a
line, which is what routing memory is searched by."""

import json

from pydantic import BaseModel, Field

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register
from overheard.memory.store import teams_map


class ProblemOut(BaseModel):
    is_problem: bool
    problem_type: str            # one of the known kinds (root causes), or "other"
    statement: str               # the problem, in one line
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]


@_register
class problem_classify:
    name = "problem_classify"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        kinds = sorted(k for k in teams_map()["causes"] if k != "junk")
        return Task(
            name=cls.name,
            description="Is it a problem a team must act on?",
            system=("You read voicemail left at a federal benefits-service call center and decide whether it reports a "
                    "problem a back-office team has to act on (a held or returned payment, a broken sign-in, a records "
                    "or congressional request, fraud, a letter people can't follow) or something answered on the call "
                    "(a status question, a thank-you, a wrong number). Reply with only a JSON object: {\"is_problem\": "
                    "bool, \"problem_type\": string, \"statement\": string, \"confidence\": number 0-1, \"reasons\": "
                    "[string]}. problem_type is one of " + json.dumps(kinds) + " or \"other\". statement is the "
                    "problem in one plain line. reasons quote the message."),
            user=f"Voicemail transcript:\n{v.script}\n\nIs it a problem a team must act on?",
            output_model=ProblemOut,
            examples=[
                {"role": "user", "content": "My payment came back to you, the bank closed my account."},
                {"role": "assistant", "content": json.dumps(
                    {"is_problem": True, "problem_type": "returned-deposit", "statement": "A deposit came back: the "
                     "caller's bank account was closed.", "confidence": 0.9, "reasons": ["\"my payment came back\""]})},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
