"""Stage [D]: does a policy, program, notice, outage or deadline apply to this voicemail? Retrieval
(pipeline/applies.py) picks the few rules in force today that look closest; this task decides each one: applies,
doesn't apply, or unsure, with a reason and the words from the transcript it rests on."""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class Verdict(BaseModel):
    rule_id: str
    verdict: Literal["applies", "does_not_apply", "unsure"]
    reason: str
    quote: str = ""              # the transcript's own words it rests on (required for "applies")


class AppliesOut(BaseModel):
    verdicts: list[Verdict]


@_register
class applies_triage:
    name = "applies_triage"

    @classmethod
    def build(cls, v: Voicemail, rules: list[dict]) -> Task:
        lines = "\n".join(f"- {r['id']}: {r['name']}. {r['description']} Applies to e.g. "
                          f"{json.dumps(r['examples']['applies'])}; not to {json.dumps(r['examples']['not'])}"
                          for r in rules)
        return Task(
            name=cls.name,
            description="Which policies, programs or known issues apply?",
            system=("You read voicemail left at a federal benefits-service call center and decide, for each rule "
                    "given (a policy, program, notice, outage or deadline in force today), whether it applies to "
                    "this caller. Reply with only a JSON object: {\"verdicts\": [{\"rule_id\": string, \"verdict\": "
                    "\"applies\" | \"does_not_apply\" | \"unsure\", \"reason\": string, \"quote\": string}]}, one "
                    "verdict per rule. quote is the caller's exact words the verdict rests on, copied from the "
                    "transcript; an \"applies\" must have one. Say \"unsure\" when it could go either way, and why."),
            user=f"Voicemail transcript:\n{v.script}\n\nRules in force today:\n{lines}\n\nWhich apply?",
            output_model=AppliesOut,
            examples=[],
            context=json.dumps({**v.truth.model_dump(mode="json"), "script": v.script, "rules": rules},
                               ensure_ascii=False),
        )
