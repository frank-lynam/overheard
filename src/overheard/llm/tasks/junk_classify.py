"""Is this voicemail junk (a robocall, a scam, a wrong number, a pocket dial) or a real caller? Unsure goes to a
person: missing a real problem is worse than letting junk through."""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class JunkOut(BaseModel):
    verdict: Literal["junk", "not_junk", "unsure"]
    reason: str


@_register
class junk_classify:
    name = "junk_classify"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Is the voicemail junk or a real caller?",
            system=("You screen voicemail left for a federal benefits-service call center before a person hears it. "
                    "Reply with only a JSON object: {\"verdict\": \"junk\" | \"not_junk\" | \"unsure\", \"reason\": "
                    "string}. junk: robocalls, sales pitches, prize and impersonation scams, wrong numbers meant for "
                    "someone else, pocket dials and silence. not_junk: anyone who could be a benefits caller, however "
                    "short, garbled or rude. When in doubt, unsure: a person will listen. Never call a real caller "
                    "junk because the line was bad or the message was brief. reason is one sentence."),
            user=f"Voicemail transcript:\n{v.script}\n\nIs it junk?",
            output_model=JunkOut,
            examples=[
                {"role": "user", "content": "Your vehicle's extended warranty is about to expire. Press one now."},
                {"role": "assistant", "content": json.dumps({"verdict": "junk", "reason": "A scripted warranty robocall."})},
                {"role": "user", "content": "Can't log in... error... call me... five five five."},
                {"role": "assistant", "content": json.dumps(
                    {"verdict": "not_junk", "reason": "A caller with a sign-in problem on a bad line."})},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
