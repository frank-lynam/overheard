"""Draft the agent's callback response. The human approves before anything goes out."""

import json

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class DraftOut(BaseModel):
    text: str
    tone: str  # e.g. "polite", "reassuring", "apologetic"
    signsOff: bool  # True if the draft closes with a sign-off (the human may still edit it)


@_register
class draft_reply:
    name = "draft_reply"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Draft the agent's callback message. A human approves before it goes out.",
            system=("You draft the callback message an agent would read to a caller at a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"text\": string, \"tone\": string, \"signsOff\": boolean}. "
                    "The text is one short spoken paragraph: greet the caller by first name when it is known, "
                    "confirm the thing they asked about, say what happens next and by when, and close politely. "
                    "It is always a draft: never claim the issue is resolved, never invent facts that are not in the "
                    "transcript, and never promise a specific date unless the transcript contains one. "
                    "signsOff is true when the draft ends with a closing line such as 'Thank you for your patience.'"),
            user=(f"Voicemail transcript ({'English' if v.lang == 'en' else v.lang}):\n{v.script}\n\n"
                  "Draft the callback message."),
            output_model=DraftOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (English):\nHi, it's Karen, case number FBS 110012. My "
                                            "May payment hasn't shown up and I was told it would be there by the 3rd."},
                {"role": "assistant", "content": json.dumps(
                    {"text": "Hi Karen, this is the Federal Benefits Service Center calling about case FBS-110012. I've "
                              "been looking into your May payment that was expected by the 3rd, and I can walk you through "
                              "where it stands. Please let me know if the number I have is still the best way to reach "
                              "you. Thank you for your patience.",
                     "tone": "polite", "signsOff": True})},
            ],
            context=json.dumps(v.truth.model_dump(mode="json"), ensure_ascii=False),
        )
