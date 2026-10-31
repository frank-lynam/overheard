"""Throwaway mode-1 browser probe: boots the real app on a throwaway port with a
seeded throwaway db, loads the real js/css with a probe page, and dumps what it saw."""

import json
import os
import re
import subprocess
import time
import urllib.request
from importlib.resources import files
from pathlib import Path

from overheard.data.generator import seed

db = Path("/tmp/probe-mode1.db")
db.unlink(missing_ok=True)
seed(db, 2026)  # seed BEFORE the server boots: it takes its date and rows from the file
served = Path(files("overheard") / "static")
HTML = """<html><head><meta charset="utf-8"></head><body>
  <header class="topbar"><nav class="stepper">
  <button data-mode="0" aria-pressed="true">0</button><button data-mode="1">1</button>
  <button data-mode="2">2</button><button data-mode="3">3</button></nav>
  <div class="scoreboard"></div></header>
  <p class="later" hidden></p>
  <main class="workbench"><section class="pane queue"></section><section class="pane message"
    ></section><section class="pane context"></section></main>
  <script type="module" src="js/main.js"></script>
  <script>
    const errs = [];
    addEventListener("error", e => errs.push("ERR " + e.message));
    addEventListener("unhandledrejection", e => errs.push("REJ " + String(e.reason && e.reason.stack || e.reason)));
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    (async () => {
      for (let i = 0; i < 100 && document.querySelectorAll(".queue-row").length < 60; i++) await sleep(50);
      document.querySelector('button[data-mode="1"]').click();
      await sleep(3000);
      const rows = [...document.querySelectorAll(".queue-row")];
      rows[0] && rows[0].click();
      await sleep(4000);
      const out = {
        errs,
        topRow: rows[0] ? [...rows[0].children].map(c => c.textContent).join("|") : null,
        topId: rows[0] ? rows[0].dataset.id : null,
        urgCount: document.querySelectorAll(".queue-row .urg").length,
        teamCount: document.querySelectorAll(".queue-row .team").length,
        panels: [...document.querySelectorAll(".ai-panel")].map(p => p.dataset.panel),
        badges: [...new Set([...document.querySelectorAll(".prov")].map(b => b.className.replace("prov ", "")))],
        edited: document.querySelectorAll(".word-edited").length,
        watched: document.querySelectorAll(".word-watch").length,
        accuracy: document.querySelector(".scoreboard").textContent.includes("AI accuracy"),
      };
      const pre = document.createElement("pre"); pre.id = "dbg";
      pre.textContent = JSON.stringify(out); pre.dataset.state = "done";
      document.body.appendChild(pre);
    })();
  </script>
</body></html>"""
PORT = 8814
probe = served / "__probe3.html"
probe.write_text(HTML)
env = {**os.environ, "OVERHEARD_DB_PATH": str(db)}
log = open("/tmp/probe3.log", "w")
proc = subprocess.Popen(
    ["./.venv/bin/python", "-m", "uvicorn", "overheard.app:create_app", "--factory",
     "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
    stdout=log, stderr=subprocess.STDOUT, cwd="/home/bob/work/tickets/fancy-wombat/repo", env=env)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    res = subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--virtual-time-budget=25000", "--dump-dom", f"http://127.0.0.1:{PORT}/__probe3.html"],
        capture_output=True, text=True, timeout=180)
    m = re.search(r'<pre id="dbg"[^>]*>(.*?)</pre>', res.stdout, re.S)
    if m:
        out = json.loads(m.group(1).replace("&amp;", "&"))
        print(json.dumps(out, indent=1))
        assert out["errs"] == [], out["errs"]
        assert len(out["panels"]) == 7, out["panels"]
        assert out["urgCount"] == 60 and out["teamCount"] == 60
        assert out["topId"] == "m37", out["topId"]
        assert out["accuracy"]
        assert out["watched"] > 0, out["watched"]
        print("PROBE3 OK")
    else:
        print("NO DBG; dom head:", res.stdout[:600])
        print("stderr:", res.stderr[:300])
        raise SystemExit(1)
finally:
    proc.terminate()
    proc.wait(timeout=10)
    probe.unlink(missing_ok=True)
    log.close()
