"""Run all 7 mock tasks over today's 60 voicemails; report accuracy + span sanity."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import json  # noqa: E402

from overheard.data.models import Voicemail  # noqa: E402
from overheard.llm.mock import MockProvider  # noqa: E402
from overheard.llm.tasks import TASKS  # noqa: E402

TASK_ORDER = ("summary", "extraction", "intent_urgency", "routing", "translation", "sentiment", "draft_reply")
SEED_PATH = "src/overheard/data/seed_today.json"


async def main() -> None:
    prov = MockProvider()
    vms = [Voicemail.model_validate(t) for t in json.loads(Path(SEED_PATH).read_text())["voicemails"]]
    bad = []
    acc = {"intent_urgency": 0, "routing": 0, "extraction": 0}
    n = len(vms)
    for v in vms:
        truth = v.truth
        for name in TASK_ORDER:
            task = TASKS[name].build(v)
            raw = await prov.complete(task, "mock-model")
            data = task.output_model.model_validate_json(raw)
            if name == "intent_urgency":
                if data.intent == truth.intent and data.urgency == truth.urgency:
                    acc["intent_urgency"] += 1
                else:
                    bad.append((v.id, "intent", data.intent, data.urgency, truth.intent, truth.urgency))
            elif name == "routing":
                if data.team == truth.team:
                    acc["routing"] += 1
                else:
                    bad.append((v.id, "routing", data.team, truth.team))
            elif name == "extraction":
                out = data.model_dump()
                ok = True
                for f in ("caller", "callbackNumber", "caseId", "program", "requestedAction"):
                    env = out[f]
                    span = env.get("span")
                    if span is not None:
                        s, e = span
                        if s < 0 or e > len(v.script) or not v.script[s:e].strip():
                            bad.append((v.id, f"span:{f}", v.script[max(0, s):e], f))
                            ok = False
                    true_val = getattr(truth, "callerName" if f == "caller" else f, None)
                    if f in ("caller", "callbackNumber", "caseId"):
                        if env.get("value") is not None and true_val is not None and env["value"] != true_val:
                            bad.append((v.id, f, env["value"], true_val))
                            ok = False
                if ok:
                    acc["extraction"] += 1
    print(f"messages:     {n}")
    for k, v in acc.items():
        print(f"{k:18s} {v}/{n} = {v / n:.2f}")
    print(f"problems:     {len(bad)}")
    for b in bad[:25]:
        print("  ", b)
    # the specific regression: m01 must want a call back
    task = TASKS["extraction"].build(vms[0])
    raw = await prov.complete(task, "mock-model")
    ra = task.output_model.model_validate_json(raw).requestedAction
    print("m01 requestedAction:", ra)
    assert "call" in (ra.value or ""), "m01 must be a call-back"


asyncio.run(main())
