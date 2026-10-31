"""Read the caller's tone: sentiment and whether the call needs follow-up."""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class SentimentOut(BaseModel):
    sentiment: Literal["calm", "mildly frustrated", "frustrated", "worried", "anxious"]
    escalation: Literal["standard", "follow-up"]  # follow-up: tone or stakes say don't just log it and move on


@_register
class sentiment:
    name = "sentiment"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Read the caller's tone and whether it needs follow-up.",
            system=("You read the tone of voicemail messages for a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"sentiment\": one of [\"calm\", \"mildly frustrated\", \"frustrated\", \"worried\", \"anxious\"], "
                    "\"escalation\": \"standard\" or \"follow-up\"}. "
                    "escalation is \"follow-up\" when the caller's worry, anger or the stakes of the issue "
                    "mean it should not just be logged and left to the usual queue."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Read the tone."),
            output_model=SentimentOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHi, just a quick note that the letter I sent "
                                            "last week is in, so you should have it by now. Thanks!"},
                {"role": "assistant", "content": '{"sentiment": "calm", "escalation": "standard"}'},
                {"role": "user", "content": "Voicemail transcript (English):\nIt's me again, this is my fourth time "
                                            "calling. The rent is due in three days and I still don't have my check. I "
                                            "can't keep doing this."},
                {"role": "assistant", "content": '{"sentiment": "frustrated", "escalation": "follow-up"}'},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
