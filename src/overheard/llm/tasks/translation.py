"""Translate a voicemail to English when it isn't already."""

import json

from pydantic import BaseModel

from overheard.data.models import Voicemail
from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class TranslationOut(BaseModel):
    translated: bool
    text: str  # the English text, or the original when translated is False
    sourceLang: str


@_register
class translation:
    name = "translation"

    @classmethod
    def build(cls, v: Voicemail) -> Task:
        return Task(
            name=cls.name,
            description="Translate the voicemail to English.",
            system=("You translate voicemail transcripts for a benefits-service call center. "
                    "Reply with only a JSON object: "
                    "{\"translated\": boolean, \"text\": string, \"sourceLang\": string}. "
                    "If the transcript is already English, translated is false and text is the transcript unchanged. "
                    "Otherwise translate it faithfully to English, keep the facts (numbers, names, dates) intact, "
                    "and put the two-letter source language in sourceLang."),
            user=f"Voicemail transcript (language: {v.lang}):\n{v.script}\n\nTranslate it to English.",
            output_model=TranslationOut,
            examples=[
                {"role": "user", "content": "Voicemail transcript (language: es):\nHola, mi nombre es Ana. Quiero saber "
                                            "si mi pago de marzo ya salió, mi número de caso es FBS-228810."},
                {"role": "assistant", "content": json.dumps(
                    {"translated": True,
                     "text": "Hello, my name is Ana. I want to know if my March payment has already gone out; my case "
                              "number is FBS-228810.",
                     "sourceLang": "es"})},
            ],
            context=json.dumps({"lang": v.lang, "englishGist": v.truth.englishGist}, ensure_ascii=False),
        )
