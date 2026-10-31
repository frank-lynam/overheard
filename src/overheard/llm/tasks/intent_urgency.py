"""Classify the call's intent and urgency."""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register

INTENTS = [
    "portal_access", "status_payment", "status_document", "form_question", "address_change",
    "direct_deposit_change", "records_request", "congressional", "complaint", "overpayment",
    "welfare", "urgent_hardship", "other",
]


class IntentOut(BaseModel):
    intent: Literal[tuple(INTENTS)]
    urgency: int  # 1 (low) to 5 (act today)
    obligations: list[str] = []  # congressional | records | legal | welfare | discrimination


@_register
class intent_urgency:
    name = "intent_urgency"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Classify intent and urgency; flag obligations.",
            system=("You classify voicemail messages for a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"intent\": one of " + json.dumps(INTENTS) + ", \"urgency\": integer 1-5, "
                    "\"obligations\": array of any of [\"congressional\", \"records\", \"legal\", "
                    "\"welfare\", \"discrimination\"]}. "
                    "Urgency 5 means someone's day is at risk without same-day action. "
                    "obligations lists any statutory or legal obligation the message mentions, "
                    "even if it is not stated plainly (a mention of a member of Congress is congressional; "
                    "'I need all my records' is a records request)."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Classify it."),
            output_model=IntentOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHello, this is Maria. I can't log in to the "
                                            "portal, it keeps saying my code has expired, and I've tried four times today."},
                {"role": "assistant", "content": '{"intent": "portal_access", "urgency": 2, "obligations": []}'},
                {"role": "user", "content": "Voicemail transcript (English):\nHi, my name is Dave, I'm the office "
                                            "manager for Sen. Whitmore's office, calling about a constituent's case "
                                            "FBS-900212. The senator expects a written answer within the usual window."},
                {"role": "assistant",
                 "content": '{"intent": "congressional", "urgency": 4, "obligations": ["congressional"]}'},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
