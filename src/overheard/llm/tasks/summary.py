"""Summarize a voicemail in one short line, in plain English."""

import json

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class SummaryOut(BaseModel):
    summary: str


@_register
class summary:
    name = "summary"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="One-line summary of the voicemail, in English.",
            system=("You summarize voicemail messages for a benefits-service call center. "
                    "Reply with only a JSON object: {\"summary\": string}. "
                    "The summary is one plain-English line (20-40 words) saying who called and what they need, "
                    "in English even if the caller spoke another language."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Summarize it."),
            output_model=SummaryOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHi, it's Karen, case number FBS 110012. "
                                            "My May payment hasn't shown up and I was told it would be there by the 3rd."},
                {"role": "assistant", "content": json.dumps(
                    {"summary": "Karen (case FBS 110012) says her May payment, expected by the 3rd, has not arrived."})},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
