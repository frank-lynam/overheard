"""Pull the structured facts out of a voicemail, each with a confidence and the
transcript span it came from (so a person can check the AI's work)."""

import json

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class FieldOut(BaseModel):
    """One extracted fact. `span` is [start, end) character offsets into the
    transcript; null when the fact was inferred rather than heard."""
    value: str | None
    confidence: float
    span: list[int] | None = None


class ExtractionOut(BaseModel):
    caller: FieldOut
    callbackNumber: FieldOut
    caseId: FieldOut
    program: FieldOut          # which benefits program this is about (inferred when not said)
    requestedAction: FieldOut  # call back | written reply | email | no response
    caseNumberSaid: bool


@_register
class extraction:
    name = "extraction"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Extract caller, callback number, case id, program, requested action.",
            system=("You extract facts from voicemail transcripts for a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"caller\": field, \"callbackNumber\": field, \"caseId\": field, "
                    "\"program\": field, \"requestedAction\": field, \"caseNumberSaid\": boolean} where "
                    "field is {\"value\": string|null, \"confidence\": number 0-1, \"span\": [start, end]|null}. "
                    "If the caller did not say something, value is null and confidence is under 0.6. "
                    "span are the character offsets of the words the value was heard in; null when the value "
                    "was inferred (program often is, unless the caller names the program). "
                    "confidence reflects how clearly the value was said. caseId is normalized to FBS-######## "
                    "form; null if no case number was given. callbackNumber is normalized to +1-AAA-BBB-CCCC. "
                    "requestedAction is one of [\"call back\", \"written reply\", \"email\", \"no response\"]. "
                    "caseNumberSaid is true only if the caller actually stated a case number."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Extract the facts."),
            output_model=ExtractionOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHi, it's Karen, case number FBS 110012. "
                                            "Call me back at 555-0142 when you can."},
                {"role": "assistant", "content": (
                    '{"caller": {"value": "Karen", "confidence": 0.97, "span": [9, 14]}, '
                    '"callbackNumber": {"value": "+1-555-0142", "confidence": 0.9, "span": [58, 80]}, '
                    '"caseId": {"value": "FBS-110012", "confidence": 0.95, "span": [25, 45]}, '
                    '"program": {"value": null, "confidence": 0.4, "span": null}, '
                    '"requestedAction": {"value": "call back", "confidence": 0.9, "span": [49, 60]}, '
                    '"caseNumberSaid": true}')},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
