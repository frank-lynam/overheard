"""Code words: phrases that put a voicemail in front of a person at once ("attorney", "senator", "lose my
house", "hurt myself"). Plain code, no LLM: it runs the moment the transcript exists and never waits on a model.

The list (data/triggers.json) is an illustrative sample. Matching is case-folded and word-boundary aware, so
"sue" doesn't fire on "issue"; each term matches itself and the variants listed for it (plurals, say), and
nothing else. Safety categories are top priority, raise their own alert and are never filtered as junk."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files


@dataclass(frozen=True)
class TriggerHit:
    term: str            # the configured term (a variant reports the term it belongs to)
    category: str
    priority: int        # 0 first (safety)
    span: tuple[int, int]
    said: str            # the words as they appear in the transcript

    def as_dict(self) -> dict:
        return {**asdict(self), "span": list(self.span)}


class TriggerList:
    def __init__(self, data: dict):
        self.categories: dict[str, dict] = data["categories"]
        self.illustrative = bool(data.get("illustrative"))
        self.note = data.get("note", "")
        self._patterns = []
        for t in data["terms"]:
            cat = self.categories[t["category"]]
            for phrase in [t["term"], *t.get("variants", [])]:
                words = r"\s+".join(re.escape(w) for w in phrase.casefold().split())
                self._patterns.append((re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE), t["term"], t["category"],
                                       int(cat["priority"])))

    @classmethod
    def load(cls, path=None) -> TriggerList:
        raw = open(path).read() if path else (files("overheard") / "data" / "triggers.json").read_text()
        return cls(json.loads(raw))

    def scan(self, text: str) -> list[TriggerHit]:
        """Every hit, in transcript order; where two overlap, the longer one."""
        hits = [TriggerHit(term, cat, prio, (m.start(), m.end()), m.group(0))
                for rx, term, cat, prio in self._patterns for m in rx.finditer(text)]
        hits.sort(key=lambda h: (h.span[0], -(h.span[1] - h.span[0])))
        out: list[TriggerHit] = []
        for h in hits:
            if not out or h.span[0] >= out[-1].span[1]:
                out.append(h)
        return out

    def page_for(self, category: str) -> str | None:
        """Who a safety alert would page (simulated), or None."""
        return self.categories.get(category, {}).get("page")


@lru_cache(maxsize=1)
def default_list() -> TriggerList:
    return TriggerList.load()
