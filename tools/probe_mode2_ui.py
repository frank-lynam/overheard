"""Throwaway mode-2 browser probe: boots the real app on a throwaway port with a
seeded throwaway db, loads the real js/css with a probe page, flips to mode 2,
checks the incident banner / cluster badges / repeat note / resolution panel /
scoreboard-2 metrics in the DOM, and saves a screenshot."""

import json
import os
import re
import subprocess
import time
import urllib.request
from importlib.resources import files
from pathlib import Path

from overheard.data.generator import seed

db = Path("/tmp/probe-mode2.db")
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
      document.querySelector('button[data-mode="2"]').click();
      await sleep(3000);
      const rows = [...document.querySelectorAll(".queue-row")];
      const m02 = document.querySelector('.queue-row[data-id="m02"]');
      m02 && m02.click();
      for (let i = 0; i < 100 && !document.querySelector(".mode2-panels"); i++) await sleep(100);
      await sleep(2000);
      const banners = [...document.querySelectorAll(".incident-banner")].map(b => b.textContent.slice(0, 120));
      const out = {
        errs,
        rowCount: rows.length,
        clusterBadges: document.querySelectorAll(".badge.cluster").length,
        incidentBadges: document.querySelectorAll(".badge.incident").length,
        resolvableBadges: document.querySelectorAll(".badge.resolvable").length,
        obligationBadges: document.querySelectorAll(".badge.obligation").length,
        windowBadges: document.querySelectorAll(".badge.window").length,
        repeatNotes: [...document.querySelectorAll(".repeat-note")].map(n => n.title),
        banners,
        resolutionPanels: [...document.querySelectorAll(".mode2-panels .ai-panel")]
          .map(p => p.dataset.panel || p.textContent.slice(0, 40)),
        hasApprove: !!document.querySelector(".mode2-panels button"),
        score2: document.querySelector(".scoreboard").textContent.slice(0, 400),
        hasCallbacksStat: document.body.textContent.includes("Callbacks avoided"),
        hasDeadlinesStat: document.body.textContent.includes("Deadlines")
      };
      const pre = document.createElement("pre"); pre.id = "dbg";
      pre.textContent = JSON.stringify(out); pre.dataset.state = "done";
      document.body.appendChild(pre);
    })();
  </script>
</body></html>"""
PORT = 8816
probe = served / "__probe_mode2.html"
probe.write_text(HTML)
env = {**os.environ, "OVERHEARD_DB_PATH": str(db)}
log = open("/tmp/probe_mode2.log", "w")
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
         "--virtual-time-budget=25000", "--dump-dom", f"http://127.0.0.1:{PORT}/__probe_mode2.html"],
        capture_output=True, text=True, timeout=180)
    m = re.search(r'<pre id="dbg"[^>]*>(.*?)</pre>', res.stdout, re.S)
    if m:
        out = json.loads(m.group(1).replace("&amp;", "&"))
        print(json.dumps(out, indent=1))
        assert out["errs"] == [], out["errs"]
        assert out["rowCount"] >= 55, out["rowCount"]
        assert out["clusterBadges"] >= 6, out["clusterBadges"]
        assert out["incidentBadges"] >= 6, out["incidentBadges"]
        assert out["resolvableBadges"] >= 9, out["resolvableBadges"]
        assert out["obligationBadges"] >= 6, out["obligationBadges"]
        assert out["windowBadges"] >= 3, out["windowBadges"]
        assert any("m42" in t for t in out["repeatNotes"]), out["repeatNotes"]
        assert len(out["banners"]) == 1 and "portal" in out["banners"][0].lower(), out["banners"]
        assert "4012" in out["score2"], out["score2"]  # the incident title with the error code is on the scoreboard
        assert out["resolutionPanels"], out["resolutionPanels"]
        assert out["hasApprove"], "no approve button in the resolution panel"
        assert out["hasCallbacksStat"] and out["hasDeadlinesStat"], out["score2"]
        print("PROBE_MODE2 OK")
    else:
        print("NO DBG; dom head:", res.stdout[:600])
        print("stderr:", res.stderr[:300])
        raise SystemExit(1)
    out_png = Path("/home/bob/work/tickets/fancy-wombat/mode2.png")
    subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--window-size=1500,2400", "--virtual-time-budget=40000",
         f"--screenshot={out_png}", f"http://127.0.0.1:{PORT}/__probe_mode2.html"],
        capture_output=True, text=True, timeout=300)
    print("saved", out_png, out_png.stat().st_size, "bytes")
finally:
    proc.terminate()
    proc.wait(timeout=10)
    probe.unlink(missing_ok=True)
    log.close()
