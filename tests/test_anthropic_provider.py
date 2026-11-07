"""Claude as the model (plan section 8): the request AnthropicProvider makes (structured output from the task's
pydantic model, effort, the refusal fallback where it's offered), Bedrock's client and model ids, a refusal handed
to the runner's fallback, the provider chosen from the settings, and per-task models. No network: the client is
replaced by a fake that records the request."""

import asyncio
from types import SimpleNamespace

import pytest

from overheard.config import Settings
from overheard.llm import ResponseStore, build_provider
from overheard.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from overheard.llm.mock import MockProvider
from overheard.llm.provider import TASK_MODELS, Task
from overheard.llm.replay import ReplayProvider
from overheard.llm.run import run_task
from overheard.llm.tasks.junk_classify import JunkOut


def task() -> Task:
    return Task(name="junk_classify", description="d", system="Classify.", user="Voicemail transcript:\nhello\n\n?",
                output_model=JunkOut, examples=[{"role": "user", "content": "x"},
                                                {"role": "assistant", "content": '{"verdict": "junk", "reason": "r"}'}])


class FakeMessages:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def create(self, **kw):
        self.calls.append(kw)
        return self.reply


def fake(provider, text='{"verdict": "not_junk", "reason": "A caller."}', stop="end_turn"):
    reply = SimpleNamespace(stop_reason=stop, stop_details=None,
                            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])
    plain, beta = FakeMessages(reply), FakeMessages(reply)
    provider.client = SimpleNamespace(messages=plain, beta=SimpleNamespace(messages=beta))
    return plain, beta


def test_claude_api_request_is_structured_with_effort_and_fallback():
    p = AnthropicProvider(Settings(llm_provider="anthropic", llm_api_key="k", llm_effort="low"))
    plain, beta = fake(p)
    out = asyncio.run(p.complete(task(), ""))
    assert out == '{"verdict": "not_junk", "reason": "A caller."}' and not plain.calls
    req = beta.calls[0]
    assert req["model"] == "claude-opus-5-5" and req["max_tokens"] == 16000
    assert req["fallbacks"] == "default" and req["betas"] == [FALLBACK_BETA]
    assert "tool_choice" not in req and "thinking" not in req
    fmt = req["output_config"]["format"]
    assert req["output_config"]["effort"] == "low" and fmt["type"] == "json_schema"
    assert set(fmt["schema"]["required"]) == {"verdict", "reason"} and fmt["schema"]["additionalProperties"] is False
    assert req["messages"][-1] == {"role": "user", "content": task().user} and req["messages"][0]["role"] == "user"
    # a model without the server-side fallback is asked plainly
    asyncio.run(p.complete(task(), "claude-haiku-5-5"))
    assert plain.calls[0]["model"] == "claude-haiku-5-5" and "fallbacks" not in plain.calls[0]


def test_bedrock_uses_the_mantle_client_in_its_region():
    with pytest.raises(ValueError, match="AWS_REGION"):
        AnthropicProvider(Settings(llm_provider="bedrock"), bedrock=True)
    p = AnthropicProvider(Settings(llm_provider="bedrock", aws_region="us-gov-west-1"), bedrock=True)
    assert type(p.client).__name__ == "AsyncAnthropicBedrockMantle" and p.model == "anthropic.claude-opus-5-5"
    plain, beta = fake(p)
    asyncio.run(p.complete(task(), ""))
    assert plain.calls[0]["model"] == "anthropic.claude-opus-5-5" and "fallbacks" not in plain.calls[0]


def test_a_refusal_goes_to_the_runners_fallback():
    p = AnthropicProvider(Settings(llm_provider="anthropic", llm_api_key="k"))
    fake(p, text="", stop="refusal")
    assert asyncio.run(p.complete(task(), "")) is None
    t = task().model_copy(update={"context": '{"junk": null}'})
    r = asyncio.run(run_task(p, t, "claude-opus-5-5"))
    assert r.provenance == "fallback"


def test_the_provider_comes_from_the_settings(tmp_path):
    store = ResponseStore(tmp_path)
    assert isinstance(build_provider(Settings(llm_provider="anthropic"), store), MockProvider)   # mock stays mock
    live = build_provider(Settings(llm_mode="live", llm_provider="anthropic", llm_api_key="k"), store)
    assert isinstance(live, AnthropicProvider) and not live.bedrock
    rec = build_provider(Settings(llm_mode="record", llm_provider="bedrock", aws_region="us-east-1"), store)
    assert isinstance(rec, AnthropicProvider) and rec.bedrock
    assert isinstance(build_provider(Settings(llm_mode="replay", llm_provider="bedrock"), store), ReplayProvider)


def test_per_task_models_key_the_store_and_the_provenance(tmp_path):
    store = ResponseStore(tmp_path)
    models = {"junk_classify": "claude-haiku-5-5"}
    try:
        build_provider(Settings(llm_mode="mock", llm_task_models=models), store)
        assert TASK_MODELS == {}                                     # mock: one model, whatever the tasks say
        p = build_provider(Settings(llm_mode="live", llm_provider="anthropic", llm_api_key="k",
                                    llm_task_models=models), store)
        plain, beta = fake(p)
        r = asyncio.run(run_task(p, task(), "claude-opus-5-5", store, write=True))
        assert r.model == "claude-haiku-5-5" and plain.calls[0]["model"] == "claude-haiku-5-5"
        assert [f.name.split("-")[0] for f in tmp_path.glob("*.json")] == ["junk_classify"]
        assert next(tmp_path.glob("*.json")).name.endswith("claude-haiku-5-5.json")
    finally:
        TASK_MODELS.clear()
