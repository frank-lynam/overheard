"""Presenter-mode probe: boots the real app on a throwaway port, drives the
/present deck with real keydown events over CDP (headless --screenshot can't
press keys), checks the DOM of the slides, keyboard nav, assumptions panel and
speed control, and saves real screenshots of the slides as navigated."""

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets

from overheard.data.generator import seed

PORT = 8824
DB = Path("/tmp/probe-present.db")
BASE = f"http://127.0.0.1:{PORT}"
REPO = Path(__file__).resolve().parent.parent
# NOTE: snap chromium's --screenshot vanishes into its private /tmp; real paths only.
SHOTS = {
    "root-causes": REPO / "rehearse_present_rootcauses.png",
    "promises": REPO / "rehearse_present_promises.png",
    "staffing": REPO / "rehearse_present_staffing.png",
}
SLIDES = ["root-causes", "event-impact", "journeys", "promises", "equity",
          "letter-lab", "ask", "knowledge-gaps", "weak-signals", "staffing-forecast"]
N = len(SLIDES)

env = dict(os.environ)
env.setdefault("DISPLAY", "")

DB.unlink(missing_ok=True)
seed(DB, 2026)
env.update(OVERHEARD_DB_PATH=str(DB), OVERHEARD_LLM_MODE="mock")


def key_js(k: str) -> str:
    return f"""(async () => {{
        document.body.focus();
        document.body.dispatchEvent(new KeyboardEvent("keydown", {{key: "{k}", bubbles: true, cancelable: true}}));
        await new Promise(r => setTimeout(r, 3500));  // let the load + reveal settle
        return document.querySelector("#p-count").textContent;
    }})()"""


async def main():
    server = subprocess.Popen(
        ["./.venv/bin/python", "-m", "uvicorn", "overheard.app:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        env=env, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("server never came up")

        chromium = subprocess.Popen(
            ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
             "--remote-debugging-port=9333", "--window-size=1400,900", BASE + "/present"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ws_url = None
            for _ in range(100):
                try:
                    data = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=1))
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
                    r = await send("Runtime.evaluate", expression=expr,
                                   returnByValue=True, awaitPromise=True)
                    return r.get("result", {}).get("value")

                async def shot(path: Path):
                    # virtual time doesn't run under CDP; real time does, so the
                    # reveal transitions have already settled (we waited 3.5s/slide)
                    r = await send("Page.captureScreenshot", format="png")
                    path.write_bytes(base64.b64decode(r["data"]))

                await send("Page.enable")
                boot = await js("""(async () => {
                    const t0 = Date.now();
                    while (Date.now() - t0 < 30000) {
                        const el = document.querySelector(".p-slide .m3-headline");
                        if (el) return el.textContent;
                        await new Promise(r => setTimeout(r, 250));
                    }
                    return "TIMEOUT: " + document.title;
                })()""")

                out = {"boot": boot}
                out["slide1"] = await js("""(() => {
                    const slide = document.querySelector(".p-slide");
                    return {
                        count: document.querySelector("#p-count").textContent,
                        headline: (slide.querySelector(".m3-headline") || {}).textContent || "",
                        rows: slide.querySelectorAll("table tbody tr").length,
                        bars: slide.querySelectorAll("rect").length,
                        prov: (slide.querySelector(".prov") || {}).textContent || "",
                        dots: document.querySelectorAll(".p-dot").length,
                        activeDots: document.querySelectorAll(".p-dot.active").length,
                    };
                })()""")
                await shot(SHOTS["root-causes"])

                # keyboard: ArrowRight through the whole deck
                for i in range(1, N):
                    out[f"count_{i}"] = await js(key_js("ArrowRight"))
                out["last"] = await js("""(() => {
                    const slide = document.querySelector(".p-slide");
                    return {
                        headline: (slide.querySelector(".m3-headline") || {}).textContent || "",
                        rows: slide.querySelectorAll("table tbody tr").length,
                        count: document.querySelector("#p-count").textContent,
                    };
                })()""")
                await shot(SHOTS["staffing"])
                # Home back to the start, number jump to promises (slide 4)
                out["home"] = await js(key_js("Home"))
                out["jump4"] = await js(key_js("4"))
                out["promises"] = await js("""(() => {
                    const slide = document.querySelector(".p-slide");
                    return {
                        count: document.querySelector("#p-count").textContent,
                        headline: (slide.querySelector(".m3-headline") || {}).textContent || "",
                        rows: slide.querySelectorAll("table tbody tr").length,
                    };
                })()""")
                await shot(SHOTS["promises"])
                # assumptions panel with 'a'
                out["assume"] = await js("""(async () => {
                    document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "a", bubbles: true}));
                    await new Promise(r => setTimeout(r, 3500));
                    const panel = document.querySelector("#p-assumptions-panel");
                    const facts = document.querySelector("#p-assume-facts");
                    return {
                        open: !panel.hidden,
                        rows: facts ? facts.querySelectorAll("dt").length : 0,
                        text: facts ? facts.textContent : "",
                    };
                })()""")
                # close it again, switch the speed to fast, check the var follows
                out["speed"] = await js("""(async () => {
                    document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "a", bubbles: true}));
                    const sel = document.querySelector("#p-speed");
                    sel.value = "fast";
                    sel.dispatchEvent(new Event("change", {bubbles: true}));
                    await new Promise(r => setTimeout(r, 500));
                    return {
                        bodySpeed: document.body.dataset.speed,
                        revealStep: getComputedStyle(document.body).getPropertyValue("--reveal-step"),
                    };
                })()""")

        finally:
            chromium.terminate()
            try:
                chromium.wait(timeout=5)
            except Exception:
                chromium.kill()

        # ---- assertions -----------------------------------------------------------
        assert "form 22b" in out["boot"].lower(), out["boot"]
        assert out["slide1"]["dots"] == N, out["slide1"]
        assert out["slide1"]["activeDots"] == 1, out["slide1"]
        assert out["slide1"]["rows"] == 10, out["slide1"]
        assert out["slide1"]["bars"] >= 12, out["slide1"]
        assert "form 22b" in out["slide1"]["headline"].lower(), out["slide1"]
        assert "plain code" in out["slide1"]["prov"], out["slide1"]
        for i in range(1, N):
            assert out[f"count_{i}"] == f"{i + 1} / {N}", (i, out[f"count_{i}"])
        assert out["home"] == "1 / 10", out["home"]
        assert out["jump4"] == "4 / 10", out["jump4"]
        assert out["promises"]["rows"] >= 5, out["promises"]
        assert out["last"]["rows"] >= 2, out["last"]
        assert out["assume"]["open"] is True, out["assume"]
        assert out["assume"]["rows"] == 7, out["assume"]
        assert "3.5" in out["assume"]["text"] and "$75" in out["assume"]["text"], out["assume"]["text"]
        assert out["speed"]["bodySpeed"] == "fast", out["speed"]
        assert out["speed"]["revealStep"].strip() in ("80ms", "0.08s"), out["speed"]
        for p in SHOTS.values():
            assert p.exists() and p.stat().st_size > 10_000, (p, p.stat().st_size if p.exists() else 0)
        print(json.dumps(out, indent=2, default=str))
        print("PROBE_PRESENTER OK")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    asyncio.run(main())
