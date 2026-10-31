"""Route the call to the right team queue, with a one-sentence reason."""

import json
from typing import Literal

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register

TEAMS = ["portal_support", "accounts", "payments", "correspondence", "documents", "general", "escalations"]


class RoutingOut(BaseModel):
    team: Literal[tuple(TEAMS)]
    reason: str


@_register
class routing:
    name = "routing"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        t = v.truth.model_dump(mode="json")
        return Task(
            name=cls.name,
            description="Route the voicemail to a team queue.",
            system=("You route voicemail messages at a benefits-service call center to the team that should "
                    "work them. Reply with only a JSON object: {\"team\": string, \"reason\": string}. "
                    "team is one of " + json.dumps(TEAMS) + ": "
                    "portal_support (website and sign-in problems), accounts (case and address records, letters), "
                    "payments (money coming in or going out, deposits, overpayments), correspondence "
                    "(congressional offices, records requests, appeals, holds), documents (confirming or "
                    "submitting paperwork), general (everything else), escalations (urgent hardship, welfare "
                    "and safety concerns). "
                    "reason is one sentence: why this team, from the message. "
                    "When urgency is 5, route to escalations regardless of the topic."),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  f"The classifier rated this intent {t.get('intent', 'other')} and "
                  f"urgency {t.get('urgency', 2)} of 5. Route it."),
            output_model=RoutingOut,
            examples=[
                {"role": "user", "content": "The classifier rated this intent status_payment and urgency 4 of 5. "
                                            "My March payment didn't come and my power is being shut off Friday."},
                {"role": "assistant", "content": json.dumps(
                    {"team": "escalations",
                     "reason": "Urgency is 5: a power shut-off Friday needs same-day action."})},
                {"role": "user", "content": "The classifier rated this intent portal_access and urgency 2 of 5. "
                                            "I keep getting an error when I log in."},
                {"role": "assistant", "content": json.dumps(
                    {"team": "portal_support", "reason": "A sign-in error is the portal team's problem."})},
            ],
            context=json.dumps(t, ensure_ascii=False),
        )
