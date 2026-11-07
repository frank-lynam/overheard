"""AnthropicProvider: Claude, through the official `anthropic` SDK, on the Claude API or on Amazon Bedrock.

- `OVERHEARD_LLM_PROVIDER=anthropic`: the Claude API (`AsyncAnthropic`). The key is `OVERHEARD_LLM_API_KEY` if set,
  else the SDK's own credential chain (`ANTHROPIC_API_KEY`, an `ant auth login` profile, ...);
  `OVERHEARD_LLM_BASE_URL`, if set, points it at another Anthropic endpoint.
- `OVERHEARD_LLM_PROVIDER=bedrock`: Amazon Bedrock (`AsyncAnthropicBedrockMantle`, the Messages API on Bedrock), in
  `OVERHEARD_AWS_REGION` (for example `us-gov-west-1`) with the usual AWS credential chain. Model ids take the
  `anthropic.` prefix. Which Claude models a region offers is AWS's list, not an assumption here.

Structured output is the API's own (`output_config.format` with the task's pydantic model as a strict JSON
schema), not a forced tool call: current models reject forced `tool_choice`. Effort is set explicitly
(`OVERHEARD_LLM_EFFORT`, default medium). On the Claude API, models that support it get the server-side refusal
fallback (`fallbacks: "default"`); a refusal that still comes back returns nothing, and the shared runner puts in
the from-truth stand-in marked `fallback`, as for any failed answer. Record and replay work as for any provider:
the runner keeps and reads the raw text."""

from __future__ import annotations

import logging
from typing import Any

from overheard.config import Settings
from overheard.llm.provider import Task

log = logging.getLogger("overheard.llm")

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that take the server-side `fallbacks: "default"` on the Claude API (not on Bedrock).
FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


class AnthropicProvider:
    name = "live"

    def __init__(self, settings: Settings, bedrock: bool = False) -> None:
        from anthropic import transform_schema  # imported here: mock and replay never need the SDK loaded
        self._schema = transform_schema
        self.bedrock = bedrock
        if bedrock:
            if not settings.aws_region:
                raise ValueError("OVERHEARD_AWS_REGION is required for OVERHEARD_LLM_PROVIDER=bedrock")
            from anthropic import AsyncAnthropicBedrockMantle
            self.client = AsyncAnthropicBedrockMantle(aws_region=settings.aws_region, timeout=settings.llm_timeout)
            self.model = settings.llm_model or f"anthropic.{DEFAULT_MODEL}"
        else:
            from anthropic import AsyncAnthropic
            kw: dict[str, Any] = {"timeout": settings.llm_timeout}
            if settings.llm_api_key:
                kw["api_key"] = settings.llm_api_key.get_secret_value()
            if settings.llm_base_url:
                kw["base_url"] = settings.llm_base_url
            self.client = AsyncAnthropic(**kw)
            self.model = settings.llm_model or DEFAULT_MODEL
        self.effort = settings.llm_effort

    def request(self, task: Task, model: str) -> dict[str, Any]:
        """The Messages API request for a task (separate, so the tests can check it without a network)."""
        req: dict[str, Any] = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "system": task.system,
            "messages": [*task.examples, {"role": "user", "content": task.user}],
            "output_config": {"effort": self.effort,
                              "format": {"type": "json_schema", "schema": self._schema(task.output_model)}},
        }
        if not self.bedrock and model in FALLBACK_MODELS:
            req |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        return req

    async def complete(self, task: Task, model: str) -> str | None:
        req = self.request(task, model or self.model)
        if "betas" in req:
            resp = await self.client.beta.messages.create(**req)
        else:
            resp = await self.client.messages.create(**req)
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            log.warning("%s refused %s (%s)", req["model"], task.name, getattr(details, "category", None))
            return None
        return next((b.text for b in resp.content if b.type == "text"), None)
