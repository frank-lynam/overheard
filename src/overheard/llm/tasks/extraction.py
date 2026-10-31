"""Pull the structured facts out of a voicemail: caller, callback number, case id."""

import json

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class ExtractionOut(BaseModel):
    callerName: str | None
    callbackNumber: str | None
    caseId: str | None
    caseNumberSaid: bool


@_register
class extraction:
    name = "extraction"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Extract caller name, callback number, case id from the voicemail.",
            system=("You extract facts from voicemail transcripts for a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"callerName\": string|null, \"callbackNumber\": string|null, \"caseId\": string|null, "
                    "\"caseNumberSaid\": boolean}. "
                    "If the caller did not say something, the field is null. caseId is normalized to "
                    "FBS-######## form; null if no case number was given. "
                    "caseNumberSaid is true only if the caller actually stated a case number."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Extract the facts."),
            output_model=ExtractionOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHi, it's Karen, case number FBS 110012. "
                                            "Call me back at 555-0142 when you can."},
                {"role": "assistant", "content": (
                    '{"callerName": "Karen", "callbackNumber": "555-0142", "caseId": "FBS-110012", '
                    '"caseNumberSaid": true}')},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
