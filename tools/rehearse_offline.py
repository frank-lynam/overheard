"""The offline rehearsal dry run: seed, `record` the day through the real
pipeline (mock provider, write=True), then serve the *recorded* store in
replay mode with **no external network** and prove the whole app answers
entirely from the fixtures.

The network cut is in-process and airtight: the replay server runs with a
`sitecustomize.py` on its `PYTHONPATH` that patches the socket class so any
`connect()` to anything that isn't a local UNIX pipe kills the process with
`NETCUT: ...`. Binding the listener is allowed (you have to), opening a
channel to the outside world is not: every outbound request (an LLM base URL,
a DNS lookup, a stray import's update check) would make a fresh socket and
connect — and that is what the cut catches. The fixture store the server is
pointed at must also come back byte-identical (replay only reads).

Usage: ./.venv/bin/python tools/rehearse_offline.py [--no-cd]
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK = Path(__file__).resolve().parent / ".rehearsal"
SHOTS = WORK / "shots"
NETCUT = WORK / "netcut"
PORT = 8825
BASE = f"http://127.0.0.1:{PORT}"

NETCUT_SRC = """
import socket

_real_socket = socket.socket

class _Cut(_real_socket):
    def connect(self, address):
        if self.family != socket.AF_UNIX:
            raise RuntimeError(f"NETCUT: socket.connect({address!r}) in the replay server")
        return super().connect(address)

socket.socket = _Cut
"""


def wait_http(url: str, tries: int = 100) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit(f"never came up: {url}")


def api(path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode())
    print(f"  {('POST' if body else 'GET')} {path} -> 200")
    return out


async def present_over_cdp():
    """Drive the /present deck in chromium over CDP and screenshot the slides."""
    import websockets

    chromium = subprocess.Popen(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--remote-debugging-port=9334", "--window-size=1400,900", BASE + "/present"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(100):
            try:
                data = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json", timeout=1))
                page = next((t for t in data if t.get("type") == "page"), None)
                if page:
                    ws_url = page["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)
        assert ws_url, "no CDP target"

        async with websockets.connect(ws_url, max_size=64 * 2**20) as ws:
            msg_id = 0

            async def send(method, **params):
                nonlocal msg_id
                msg_id += 1
                await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == msg_id:
                        return r.get("result", {})

            async def js(expr):
                r = await send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                return r.get("result", {}).get("value")

            async def shot(path: Path):
                r = await send("Page.captureScreenshot", format="png")
                path.write_bytes(base64.b64decode(r["data"]))

            await send("Page.enable")
            # wait for the deck to have its first headline
            headline = await js("""(async () => {
                const t0 = Date.now();
                while (Date.now() - t0 < 30000) {
                    const el = document.querySelector(".p-slide .m3-headline");
                    if (el) return el.textContent;
                    await new Promise(r => setTimeout(r, 250));
                }
                return "TIMEOUT: " + document.title;
            })()""")
            assert "form 22b" in headline.lower(), headline
            print(f"  /present booted in replay: {headline[:70]}...")
            await js("new Promise(r => setTimeout(r, 3500))")  # let slide 1's reveal settle
            await shot(SHOTS / "rehearse_replay_rootcauses.png")
            # arrow through the rest of the deck, screenshot the last slide
            count = "1 / 10"
            for _ in range(9):
                count = await js("""(async () => {
                    document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));
                    await new Promise(r => setTimeout(r, 3500));
                    return document.querySelector("#p-count").textContent;
                })()""")
            assert count == "10 / 10", count
            await shot(SHOTS / "rehearse_replay_staffing.png")
            return headline
    finally:
        chromium.terminate()
        try:
            chromium.wait(timeout=5)
        except Exception:
            chromium.kill()


def main():
    use_cdp = "--no-cd" not in sys.argv

    WORK.mkdir(exist_ok=True)
    (WORK / "fixtures").mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    NETCUT.mkdir(parents=True, exist_ok=True)
    (NETCUT / "sitecustomize.py").write_text(NETCUT_SRC)
    db = WORK / "rehearsal.db"
    db.unlink(missing_ok=True)
    for old in (WORK / "fixtures").glob("*.json"):
        old.unlink()

    # ---- 1. record the day (mock provider, write=True) ---------------------------
    from overheard.config import Settings
    from overheard.llm.record import record_day

    rec_settings = Settings(llm_mode="mock", llm_model="mock", db_path=db,
                            llm_responses_path=WORK / "fixtures")
    print("recording the day through the real pipeline (mock, write=True)...")
    rec = record_day(db, rec_settings)
    fixtures = len(list((WORK / "fixtures").glob("*.json")))
    print(f"  recorded {rec['llm_calls']} calls for {rec['voicemails']} messages; "
          f"{fixtures} fixtures in the store")
    assert fixtures > 0

    # the server will serve this copy of the store; it must come back unchanged
    server_store = WORK / "fixtures-serve"
    if server_store.exists():
        shutil.rmtree(server_store)
    shutil.copytree(WORK / "fixtures", server_store)

    env = dict(os.environ)
    env.update(OVERHEARD_DB_PATH=str(db), OVERHEARD_LLM_MODE="replay",
               OVERHEARD_LLM_MODEL="mock", OVERHEARD_LLM_RESPONSES_PATH=str(server_store),
               PYTHONPATH=str(NETCUT), DISPLAY="")

    server = subprocess.Popen(
        ["./.venv/bin/python", "-m", "uvicorn", "overheard.app:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "info"],
        env=env, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_http(f"{BASE}/api/health")

        # ---- 2. the API answers from the store, in replay mode ----------------
        print("network cut active; driving the API...")
        health = api("/api/health")
        assert health["llm_mode"] == "replay", health
        day = api("/api/day")
        assert day["count"] == rec["voicemails"], day
        q0 = api("/api/queue?mode=0")
        assert len(q0) == rec["voicemails"]
        mid = q0[0]["id"]
        msg = api(f"/api/messages/{mid}?mode=1")
        assert "analysis" in msg, msg.keys()
        rc = api("/api/archive/root-causes")
        assert rc["causes"] and rc["causes"][0]["cause"] == "form-22b-confusion", rc["causes"][:1]
        assert rc.get("laborRate") is not None
        ev = api("/api/archive/event-impact")
        assert len(ev["events"]) >= 2
        j = api("/api/archive/journeys")
        assert j["worst"] or j["causes"], {k: j[k] for k in ("loops", "repeatJourneys")}
        p = api("/api/archive/promises")
        assert p["causes"] and p["promiseShare"] >= 0, p["worstOffender"]
        eq = api("/api/archive/equity")
        assert eq["languages"] and eq["channels"], eq.keys()
        kg = api("/api/knowledge-gaps")
        assert kg["articles"] >= 0 and "coveragePct" in kg, kg.keys()
        ws_ = api("/api/weak-signals")
        assert ws_["headline"], ws_.keys()
        sf = api("/api/staffing-forecast")
        assert sf["weekdayBaseline"] > 0
        labs = api("/api/archive/letter-lab", {"text": "You were billed in error. No action needed."})
        assert labs["rewrite"]["questionsBefore"] is not None and labs["rewrite"]["questionsAfter"] is not None
        ask = api("/api/archive/ask", {"question": "Why did calls about the 22-B letter spike in June 2025?"})
        assert ask["understood"] is True and ask["answer"], ask

        # ---- 3. the presenter deck, driven in a real browser -------------------
        if use_cdp:
            print("driving /present in chromium over CDP...")
            asyncio.run(present_over_cdp())
            for f in ("rehearse_replay_rootcauses.png", "rehearse_replay_staffing.png"):
                pth = SHOTS / f
                assert pth.exists() and pth.stat().st_size > 10_000, (f, pth)
        else:
            print("  (skipping the browser half with --no-cd)")

        # ---- 4. the store came back untouched: replay only reads ---------------
        before = {f.name: f.read_bytes() for f in (WORK / "fixtures").glob("*.json")}
        after = {f.name: f.read_bytes() for f in server_store.glob("*.json")}
        assert before == after, "the replay server wrote to the fixture store"
        print(f"  store untouched: {len(after)} fixtures, byte-identical")
        print("REHEARSAL_OK")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    main()
