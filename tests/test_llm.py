"""The LLM layer: store, runner (validation/retry/fallback), mock determinism
and an honest accuracy band, fully offline."""

import asyncio
import json

import pytest

from overheard.config import Settings
from overheard.data.models import Voicemail
from overheard.llm.cache import ResponseStore
from overheard.llm.mock import MockProvider
from overheard.llm.provider import LLMProvider, Task, build_provider, input_hash
from overheard.llm.run import run_task
from overheard.llm.tasks import TASKS


def _vm() -> Voicemail:
    return Voicemail(
        id="m01", receivedAt="2026-10-30T09:12:00", callerId="+1-555-0101", durationSec=31,
        lang="en",
        script=("Hi, it's Karen, case number FBS 110012. My May payment hasn't shown up and I was told it would be "
                "there by the 3rd. Can you call me back at 555-0142?"),
        truth={"intent": "status_payment", "urgency": 3, "rootCause": "payment_delay", "team": "payments",
               "callerName": "Karen", "callbackNumber": "555-0142", "caseId": "FBS-110012", "caseNumberSaid": True,
               "group": None, "obligations": [], "resolvableBy": "status_lookup", "linkedTo": [],
               "callbackWindow": None, "beliefMismatch": None, "englishGist": None},
    )


@pytest.fixture()
def vms(seeded) -> list[Voicemail]:
    _, con, _ = seeded
    return [Voicemail(id=r["id"], receivedAt=r["received_at"], callerId=r["caller_id"], durationSec=r["duration_sec"],
                      lang=r["lang"], script=r["script"], truth=json.loads(r["truth"]))
            for r in con.execute("SELECT * FROM voicemails ORDER BY received_at, id")]


def test_store_roundtrip_and_miss(tmp_path):
    store = ResponseStore(tmp_path / "responses")
    assert store.get("summary", "abc", "gpt-4o-mini") is None
    store.put("summary", "abc", "gpt-4o-mini", '{"summary": "hi"}')
    assert store.get("summary", "abc", "gpt-4o-mini") == '{"summary": "hi"}'
    assert store.get("summary", "xyz", "gpt-4o-mini") is None  # different key
    # atomic write: no stray temp files left behind
    assert [p.name for p in (tmp_path / "responses").iterdir()] == ["summary-abc-gpt-4o-mini.json"]


def test_build_provider_modes(tmp_path):
    from overheard.llm.openai_compat import OpenAICompatProvider
    from overheard.llm.replay import ReplayProvider

    store = ResponseStore(tmp_path)
    assert isinstance(build_provider(Settings(llm_mode="mock"), store), MockProvider)
    replay_settings = Settings(llm_mode="replay", llm_base_url="http://x", llm_api_key="k")
    assert isinstance(build_provider(replay_settings, store), ReplayProvider)
    for mode in ("live", "record"):
        p = build_provider(Settings(llm_mode=mode, llm_base_url="http://x", llm_api_key="k"), store)
        assert isinstance(p, OpenAICompatProvider)
        assert p.name == "live"
    with pytest.raises(ValueError):
        build_provider(Settings(llm_mode="live"), store)


def test_mock_deterministic():
    task = TASKS["summary"].build(_vm())
    p = MockProvider()
    a = asyncio.run(p.complete(task, "mock"))
    b = asyncio.run(p.complete(task, "mock"))
    assert a == b
    assert isinstance(p, LLMProvider)


def test_run_task_mock_provenance(tmp_path):
    task = TASKS["summary"].build(_vm())
    result = asyncio.run(run_task(MockProvider(), task, "mock", store=ResponseStore(tmp_path)))
    assert result.provenance == "llm"
    assert result.data.summary  # validates against SummaryOut


def test_cache_hit_skips_provider(tmp_path):
    task = TASKS["summary"].build(_vm())
    store = ResponseStore(tmp_path)
    store.put(task.name, input_hash(task, "mock"), "mock", '{"summary": "from the store"}')

    class NoCall:
        name = "nocall"

        async def complete(self, t, m):
            raise AssertionError("provider was called on a cache hit")

    result = asyncio.run(run_task(NoCall(), task, "mock", store=store))
    assert result.data.summary == "from the store"
    assert result.provenance == "llm"


def test_validation_retry_then_fallback(tmp_path):
    task = TASKS["summary"].build(_vm())
    calls = []

    class Flaky:
        name = "flaky"

        async def complete(self, t, m):
            calls.append(t.user)
            return '{"summary": '  # never parseable

    result = asyncio.run(run_task(Flaky(), task, "mock", store=ResponseStore(tmp_path)))
    assert result.provenance == "fallback"
    assert len(calls) == 2  # original + one retry
    assert "could not be parsed" in calls[1]  # the error was appended


def test_retry_recoverable(tmp_path):
    task = TASKS["summary"].build(_vm())
    calls = []

    class Recover:
        name = "recover"

        async def complete(self, t, m):
            calls.append(1)
            return '{"summary": ' if len(calls) == 1 else '{"summary": "second try"}'

    result = asyncio.run(run_task(Recover(), task, "mock", store=ResponseStore(tmp_path)))
    assert result.provenance == "llm"
    assert result.data.summary == "second try"


def test_mock_offline_end_to_end(tmp_path):
    """mock mode: every task over the day's first message, no network, valid output."""
    v = _vm()
    for _name, cls in TASKS.items():
        task = cls.build(v)
        result = asyncio.run(run_task(MockProvider(), task, "mock", store=ResponseStore(tmp_path)))
        assert result.model == "mock"
        assert result.key == input_hash(task, "mock")
    # translation of an English message is the identity
    t = asyncio.run(MockProvider().complete(TASKS["translation"].build(v), "mock"))
    out = json.loads(t)
    assert out["translated"] is False and out["sourceLang"] == "en"


def test_mock_intent_accuracy_band(vms):
    """The seeded ~6% mistakes keep the scoreboard honest: not 100%, not worse than 85%."""
    p = MockProvider()
    correct = 0
    for v in vms:
        out = json.loads(asyncio.run(p.complete(TASKS["intent_urgency"].build(v), "mock")))
        if out["intent"] == v.truth.intent and out["urgency"] == v.truth.urgency:
            correct += 1
    acc = correct / len(vms)
    assert 0.85 <= acc <= 0.99, f"intent/urgency accuracy {acc:.2%} outside the honest band"


def test_mock_extraction_accuracy_band(vms):
    p = MockProvider()
    correct = 0
    for v in vms:
        out = json.loads(asyncio.run(p.complete(TASKS["extraction"].build(v), "mock")))
        if (out["callerName"] == v.truth.callerName and out["callbackNumber"] == v.truth.callbackNumber
                and out["caseId"] == v.truth.caseId):
            correct += 1
    acc = correct / len(vms)
    assert acc >= 0.80, f"extraction accuracy {acc:.2%} too low"


def test_replay_reads_store_only(tmp_path):
    from overheard.llm.replay import ReplayProvider

    store = ResponseStore(tmp_path)
    settings = Settings(llm_mode="replay")
    p = ReplayProvider(settings, store)
    v = _vm()
    task = TASKS["summary"].build(v)
    # miss: logged, None, no exception
    assert asyncio.run(p.complete(task, "gpt-4o-mini")) is None
    store.put(task.name, input_hash(task, "gpt-4o-mini"), "gpt-4o-mini", '{"summary": "replayed"}')
    assert json.loads(asyncio.run(p.complete(task, "gpt-4o-mini")))["summary"] == "replayed"


def test_generic_mock_without_context():
    """A hand-built task (no truth context) still gets a deterministic answer."""
    from overheard.llm.tasks.summary import SummaryOut

    p = MockProvider()
    task = Task(name="summary", description="d", system="s",
                user="Voicemail transcript:\nHello there, my payment is missing.", output_model=SummaryOut)
    a = asyncio.run(p.complete(task, "mock"))
    assert json.loads(a)["summary"].startswith("Voicemail transcript:")
