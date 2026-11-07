"""OpenAICompatProvider: any OpenAI-compatible host, via the openai SDK.

- `live`: store hits are read by the runner; misses go to the host.
- `record`: everything that reaches the host is also written to the store,
  so the same day can be replayed offline later.
- Capability probe: whether the host accepts `json_schema` response_format is
  found out lazily on the first live call and remembered on the client;
  startup never waits on the network. Until it's known (and in `record`
  mode, where the probe would pollute the fixtures) JSON mode is used with
  pydantic validation on the way in.
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from overheard.config import Settings
from overheard.llm.cache import ResponseStore
from overheard.llm.provider import Task, per_loop

log = logging.getLogger("overheard.llm")


def _json_schema(task: Task) -> dict[str, Any]:
    """The task's pydantic model, written out as a JSON schema the host can check against."""
    schema = task.output_model.model_json_schema()
    # strip the $defs-free core is fine; keep it as-is, most hosts accept it
    return schema


class OpenAICompatProvider:
    name = "live"

    @property
    def client(self):
        """This event loop's client (see per_loop), unless one was set (the tests' fakes)."""
        return self.__dict__.get("_client") or self._clients.get(self._make)

    @client.setter
    def client(self, value) -> None:
        self._client = value

    def __init__(self, settings: Settings, store: ResponseStore | None = None, record: bool = False) -> None:
        if not settings.llm_base_url:
            raise ValueError(f"OVERHEARD_LLM_BASE_URL is required for llm_mode={settings.llm_mode}")
        if not settings.llm_api_key:
            raise ValueError(f"OVERHEARD_LLM_API_KEY is required for llm_mode={settings.llm_mode}")
        self._make = lambda: AsyncOpenAI(base_url=settings.llm_base_url,
                                         api_key=settings.llm_api_key.get_secret_value(), timeout=settings.llm_timeout)
        self._clients = per_loop()
        self.model = settings.llm_model or "gpt-4o-mini"
        self.store = store
        self.record = record
        self._json_schema_ok: bool | None = None  # None = not probed yet

    async def complete(self, task: Task, model: str) -> str:
        if self._json_schema_ok is None:
            self._json_schema_ok = await self._probe_json_schema()
        if self._json_schema_ok:
            response_format: dict[str, Any] = {"type": "json_schema", "json_schema": {"name": f"{task.name}_output",
                                                                                        "strict": True,
                                                                                        "schema": _json_schema(task)}}
        else:
            response_format = {"type": "json_object"}
        resp = await self.client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": "system", "content": task.system},
                      *task.examples,
                      {"role": "user", "content": task.user}],
            response_format=response_format,
        )
        text = resp.choices[0].message.content or ""
        if self.record and self.store is not None:
            from overheard.llm.provider import input_hash

            self.store.put(task.name, input_hash(task, model or self.model), model or self.model, text)
        return text

    async def _probe_json_schema(self) -> bool:
        """One tiny request to find out whether json_schema response_format is honoured."""
        if self.record:
            return False  # keep the fixtures clean: record mode uses JSON mode
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
                  "required": ["ok"], "additionalProperties": False}
        try:
            await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You answer with a JSON object with exactly one field, ok, a boolean."},
                    {"role": "user", "content": 'Reply {"ok": true}.'},
                ],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "probe", "strict": True, "schema": schema}},
            )
            log.info("host supports json_schema response_format")
            return True
        except Exception as e:  # noqa: BLE001 - any rejection means "use JSON mode"
            log.info("json_schema probe failed (%s: %s); using JSON mode", type(e).__name__, e)
            return False
