"""Stage [E]: which team should own this problem? Given the problem and the evidence from routing memory (the most
similar past problems and where people finally sent them, weighted by similarity and recency), propose a team, with
how sure, citing the past tickets it relied on. Below the threshold: "unknown", and the ticket goes to general."""

import json

from pydantic import BaseModel, Field

from overheard.llm.provider import Task
from overheard.llm.tasks import _register
from overheard.memory.store import teams_map


class TeamOut(BaseModel):
    proposed_team: str           # a team slug, or "unknown"
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]          # ids of the past tickets it relied on


@_register
class team_propose:
    name = "team_propose"

    @classmethod
    def build(cls, problem_type: str, statement: str, weighed: dict) -> Task:
        teams = teams_map()["teams"]
        lines = "\n".join(f"- {e['ref']} ({e['when']}, similarity {e['similarity']}, weight {e['weight']}): "
                          f"{'a person sent it to ' if e.get('today') else 'went to '}{e['team']}"
                          f"{' TODAY' if e.get('today') else ''}: {e['text']}"
                          for e in weighed["evidence"]) or "(no similar past problems)"
        return Task(
            name=cls.name,
            description="Propose the team that should own the problem.",
            system=("You route problems reported to a federal benefits-service call center to the back-office team "
                    "that should own them, learning from where people finally sent similar past problems (corrections "
                    "count: a problem a person moved shows where it belongs). Each past problem has a weight: its "
                    "similarity, less for older ones, and five times as much for a decision a person made today, "
                    "which is the freshest word on where this kind of problem goes now. Propose the team with the "
                    "most weight unless the problem itself plainly belongs elsewhere; count weight, not how many "
                    "past problems point each way. Reply with only a JSON object: "
                    "{\"proposed_team\": string, \"confidence\": number 0-1, \"evidence\": [past ids]}. proposed_team "
                    "is one of " + json.dumps(sorted(teams)) + ", or \"unknown\" when the evidence doesn't point one "
                    "way. evidence lists the ids you relied on, from the list given."),
            user=(f"Problem ({problem_type}): {statement}\n\nSimilar past problems and where they went:\n{lines}\n\n"
                  f"Weight of the evidence by team: {json.dumps(weighed['shares'])}\n\nWhich team should own it?"),
            output_model=TeamOut,
            examples=[],
            context=json.dumps({"weighed": weighed}, ensure_ascii=False),
        )
