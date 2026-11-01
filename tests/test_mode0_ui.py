"""Mode 0 UI: the pieces the build order promises are in the front end, and the page really renders."""

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "overheard" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_the_mode_0_pieces_are_in_the_front_end():
    index = read("index.html")
    queue = read("js/ui/queue.js")
    message = read("js/ui/message.js")
    context = read("js/ui/context.js")
    scoreboard = read("js/ui/scoreboard.js")
    main = read("js/main.js")
    # Mode 0: arrival-ordered inbox, no content visible until a message is played.
    assert "arrival order" in queue and "Queue ·" in queue
    assert 'store.emit("simulate")' in queue and "simClock" in main
    # Speaking-pace transcript reveal (~150 wpm), so listening still costs what it would.
    assert re.search(r"WPM\s*=\s*150", message) and "transcript" in message
    # Manual entry form: every field the design lists.
    for field in ("callerName", "callbackNumber", "caseNumber", "category", "priority", "disposition", "notes"):
        assert field in message
    # Measured effort: real time per message.
    assert "secondsSpent" in message and "open" in message
    # Manual lookup panel against the case backend (name, phone or case number).
    assert "lookup" in context and "Name, phone or case number" in context
    # Scoreboard v1: the simulation's numbers, plus the configurable handling time
    # that extrapolates the workload clock.
    assert "Workload clock" in scoreboard and "saveAssumptions" in scoreboard and "handleMin" in scoreboard
    # The four-mode stepper, starting in Mode 0.
    for m in range(4):
        assert f'data-mode="{m}"' in index


def test_the_message_view_costs_what_the_design_says():
    message = read("js/ui/message.js")
    # Per-message workload clock: listening + handling + callback, from the assumptions.
    assert re.search(r"workloadMin\s*=\s*listenMin\s*\+\s*a\.handleMin\s*\+\s*a\.callbackMin", message)
    assert "Costs the agent" in message
    # The scoreboard's extrapolation uses the same arithmetic as the simulation.
    scoreboard = read("js/ui/scoreboard.js")
    assert "handleMin + a.callbackMin" in scoreboard


PROBE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>probe</title>
<link rel="stylesheet" href="css/app.css"></head>
<body>
  <header class="topbar"><nav class="stepper">
    <button data-mode="0">0 No AI</button><button data-mode="1">1</button>
    <button data-mode="2">2</button><button data-mode="3">3</button>
  </nav>
  <div class="scoreboard" aria-live="polite"><span class="muted">scoreboard</span></div></header>
  <main class="mode3" hidden><section class="m3-pane root-causes"></section></main>
  <main class="workbench">
    <section class="pane queue"></section>
    <section class="pane message"></section>
    <section class="pane context"></section>
  </main>
  <pre id="out" data-state="loading"></pre>
  <script type="module" src="js/main.js"></script>
  <script>
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const flat = (e) => (e ? e.textContent.replace(/\\s+/g, " ").trim() : null);
    (async () => {
      const out = { errors: [] };
      addEventListener("error", (e) => out.errors.push(String(e.message)));
      for (let i = 0; i < 100 && document.querySelectorAll(".queue-row").length < 60; i++) await sleep(100);
      out.queueRows = document.querySelectorAll(".queue-row").length;
      const row = document.querySelector(".queue-row");
      out.firstRow = { text: flat(row), fields: [...row.children].map((c) => c.className),
        touched: flat(row.querySelector(".q-touch")) };
      out.scoreboardBefore = flat(document.querySelector(".scoreboard"));
      out.workloadClock = out.scoreboardBefore.match(/Workload clock\s*\d+h ?\d*m/)?.[0] ?? null;
      row.click();
      await sleep(900);
      out.messageHead = flat(document.querySelector(".pane.message .pane-head"));
      out.workloadLine = flat(document.querySelector(".pane.message .workload"));
      out.formFields = [...document.querySelectorAll(
        ".pane.message form.entry input, .pane.message form.entry select, .pane.message form.entry textarea")]
        .map((f) => f.name);
      out.effort = flat(document.querySelector(".pane.message .effort"));
      out.lookupPlaceholder = document.querySelector(".pane.context input[type=search]")?.placeholder || null;
      // the handling time is editable and the workload clock re-extrapolates from it
      const handle = document.querySelector('.scoreboard input[aria-label="Handling minutes per message"]');
      out.handleDefault = handle?.value || null;
      handle.value = "2";
      handle.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(400);
      out.workloadAfterEdit = document.querySelector(".scoreboard").textContent
        .replace(/\s+/g, " ").trim().match(/Workload clock\s*\d+h ?\d*m/)?.[0] ?? null;
      [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Work the queue"))?.click();
      await sleep(10500);
      out.touched = document.querySelectorAll(".queue-row.touched").length;
      out.afterSim = flat(document.querySelector(".scoreboard"));
      out.urgentStamp = flat([...document.querySelectorAll(".queue-row")].find((r) => r.classList.contains("late")));
      out.state = "done";
      const root = document.getElementById("out");
      root.textContent = JSON.stringify(out);
      root.dataset.state = "done";
    })();
  </script>
</body></html>"""


SERVE = """
import sys, uvicorn
from fastapi.responses import HTMLResponse
from overheard.app import create_app

app = create_app()
probe = open(sys.argv[2], encoding="utf-8").read()
app.get("/__probe.html")(lambda: HTMLResponse(probe))
app.router.routes.insert(0, app.router.routes.pop())  # before the static mount at /
uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
"""


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """The real console served by the real server, on a free port, with a probe page added to it."""
    tmp = tmp_path_factory.mktemp("ui")
    probe = tmp / "probe.html"
    probe.write_text(PROBE, encoding="utf-8")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log = open(tmp / "server.log", "w")
    env = {**os.environ, "OVERHEARD_DB_PATH": str(tmp / "overheard.db")}
    proc = subprocess.Popen([sys.executable, "-c", SERVE, str(port), str(probe)],
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except Exception:
                if proc.poll() is not None:
                    raise AssertionError("server died at startup: " + (tmp / "server.log").read_text()) from None
                time.sleep(0.2)
        else:
            raise AssertionError("server never came up")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()


def test_the_console_renders_and_works_in_a_real_browser(live_server):
    """Headless Chromium with a virtual-time budget: the page renders, the queue fills, and
    'Work the queue' stamps the inbox and fills the scoreboard."""
    res = subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--virtual-time-budget=20000", "--dump-dom", f"{live_server}/__probe.html"],
        capture_output=True, text=True, timeout=120,
    )
    dom, dom_err = res.stdout, res.stderr
    m = re.search(r'<pre id="out" data-state="(\w+)"[^>]*>(.*?)</pre>', dom, re.S)
    assert m, f"probe never finished; len(dom)={len(dom)}; dom head: {dom[:1200]}; stderr: {dom_err[:600]}"
    out = json.loads(m.group(2).replace("&amp;", "&"))
    assert m.group(1) == "done"
    assert out["errors"] == [], out["errors"]
    assert out["queueRows"] == 60
    # the inbox shows only time, caller ID and length — no content before a message is played
    assert out["firstRow"]["fields"] == ["q-time", "q-caller", "q-dur", "q-touch"] and out["firstRow"]["touched"] == ""
    # the workload clock is on screen before anything is worked, with an editable handling time
    assert out["workloadClock"] and re.search(r"Workload clock\s*\d+h", out["workloadClock"])
    assert "Agent time" in out["scoreboardBefore"] and "$" not in out["scoreboardBefore"]
    # opening a message: header, per-message workload cost, the full entry form, the effort timer
    assert out["messageHead"] and re.search(r"\d:\d\d [ap]m", out["messageHead"])
    assert out["workloadLine"] and "Costs the agent" in out["workloadLine"] and "listening" in out["workloadLine"]
    assert out["formFields"] == [
        "callerName", "callbackNumber", "caseNumber", "category", "priority", "disposition", "notes"]
    assert out["effort"] and out["effort"].startswith("open ")
    assert out["lookupPlaceholder"] == "Name, phone or case number"
    # the handling time is editable and the workload clock re-extrapolates (10h 17m -> 8h 47m at 2 min each)
    assert out["handleDefault"] == "3.5"
    assert out["workloadAfterEdit"] == "Workload clock8h 47m"
    # "Work the queue": stamps roll down the inbox and the scoreboard fills with the day's cost
    assert out["touched"] >= 50
    assert re.search(r"Agent time\s*\d", out["afterSim"])
    assert re.search(r"Urgent caller reached\s*\d", out["afterSim"])
    assert out["urgentStamp"] and ("2:4" in out["urgentStamp"] or "pm" in out["urgentStamp"])
