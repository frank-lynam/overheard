"""The retro search's check ("Overlooked before today"): given a problem definition and past contacts that
retrieval found close to it, which are really that problem? Each confirmed one gets a reason quoting its words."""

import json

from pydantic import BaseModel

from overheard.llm.provider import Task
from overheard.llm.tasks import _register


class Match(BaseModel):
    id: str
    match: bool
    reason: str


class RetroOut(BaseModel):
    matches: list[Match]


@_register
class retro_match:
    name = "retro_match"

    @classmethod
    def build(cls, definition: dict, items: list[dict], truth: list[str] = ()) -> Task:
        lines = "\n".join(f"- {i['id']} ({i['at'][:10]}): {i['text']}" for i in items)
        examples = "\n".join(f"- {e}" for e in definition.get("examples", []))
        return Task(
            name=cls.name,
            description="Which past contacts are this problem?",
            system=("You help an analyst at a federal benefits-service call center find past contacts that were "
                    "about a problem identified today, but were overlooked at the time. For each contact given, say "
                    "whether it is the problem described. Reply with only a JSON object: {\"matches\": [{\"id\": "
                    "string, \"match\": bool, \"reason\": string}]}, one per contact. reason quotes the contact's "
                    "words. Similar wording isn't enough: it must be the same problem."),
            user=(f"The problem: {definition['description']}\nExamples from today:\n{examples}\n\n"
                  f"Past contacts:\n{lines}\n\nWhich are this problem?"),
            output_model=RetroOut,
            examples=[],
            context=json.dumps({"truth": sorted(truth), "items": items}, ensure_ascii=False),
        )
