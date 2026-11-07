"""An OpenAI-format gateway with a user's own key (how the GovCloud endpoint is reached): a local fake that checks
what a strict gateway would (the bearer key, a known response_format) answers the provider in live and record mode,
with json_schema and without it."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from overheard.config import Settings
from overheard.llm import ResponseStore, build_provider
from overheard.llm.provider import Task
from overheard.llm.run import run_task
from overheard.llm.tasks.junk_classify import JunkOut

KEY = "user-key-123"


def gateway(schema_ok: bool):
    seen: list[dict] = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "auth": self.headers.get("Authorization"), **body})
            fmt = (body.get("response_format") or {}).get("type", "text")
            if self.headers.get("Authorization") != f"Bearer {KEY}":
                return self.reply(401, {"error": {"message": "bad key"}})
            if fmt not in ("text", "json_object", "json_schema") or (fmt == "json_schema" and not schema_ok):
                return self.reply(400, {"error": {"message": f"response_format {fmt} not supported"}})
            content = '{"ok": true}' if "probe" in json.dumps(body.get("response_format")) else \
                '{"verdict": "not_junk", "reason": "A caller about their payment."}'
            self.reply(200, {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                             "choices": [{"index": 0, "finish_reason": "stop",
                                          "message": {"role": "assistant", "content": content}}]})

        def reply(self, code, obj):
            raw = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def task() -> Task:
    return Task(name="junk_classify", description="d", system="Reply with only a JSON object.",
                user="Voicemail transcript:\nhello\n\n?", output_model=JunkOut, context='{"junk": null}')


@pytest.mark.parametrize("schema_ok", [True, False])
@pytest.mark.parametrize("mode", ["live", "record"])
def test_an_openai_format_gateway_with_a_user_key(tmp_path, mode, schema_ok):
    srv, seen = gateway(schema_ok)
    try:
        s = Settings(llm_mode=mode, llm_base_url=f"http://127.0.0.1:{srv.server_port}/v1", llm_api_key=KEY,
                     llm_model="gov-claude")
        store = ResponseStore(tmp_path)
        p = build_provider(s, store)
        r = asyncio.run(run_task(p, task(), "gov-claude", store, write=mode == "record"))
        assert r.provenance == "llm" and r.data.verdict == "not_junk" and r.model == "gov-claude"
        calls = [c for c in seen if c["path"].endswith("/chat/completions")]
        assert all(c["auth"] == f"Bearer {KEY}" for c in calls)
        last = calls[-1]
        assert last["model"] == "gov-claude" and last["messages"][0]["role"] == "system"
        want = "json_schema" if schema_ok and mode == "live" else "json_object"   # record: always JSON mode
        assert last["response_format"]["type"] == want
        assert bool(list(tmp_path.glob("*.json"))) == (mode == "record")
    finally:
        srv.shutdown()


def test_calls_from_separate_event_loops(tmp_path):
    """The app runs each call in an event loop of its own: a client kept from an earlier loop must not be reused."""
    srv, seen = gateway(True)
    try:
        s = Settings(llm_mode="live", llm_base_url=f"http://127.0.0.1:{srv.server_port}/v1", llm_api_key=KEY,
                     llm_model="gov-claude")
        p = build_provider(s, ResponseStore(tmp_path))
        for _ in range(3):
            r = asyncio.run(run_task(p, task(), "gov-claude"))
            assert r.provenance == "llm"
    finally:
        srv.shutdown()
