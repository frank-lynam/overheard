"""Throwaway mode-3 browser probe: boots the real app on a throwaway port with a
seeded throwaway db, loads the real js/css with a probe page, flips to mode 3,
checks the archive headline / Pareto SVG / table in the DOM, and saves a screenshot."""

import json
import os
import re
import subprocess
import time
import urllib.request
from importlib.resources import files
from pathlib import Path

from overheard.data.generator import seed

db = Path("/tmp/probe-mode3.db")
db.unlink(missing_ok=True)
seed(db, 2026)  # seed BEFORE the server boots: it takes its date and rows from the file
served = Path(files("overheard") / "static")
HTML = """<html><head><meta charset="utf-8"></head><body>
  <header class="topbar"><nav class="stepper">
  <button data-mode="0" aria-pressed="true">0</button><button data-mode="1">1</button>
  <button data-mode="2">2</button><button data-mode="3">3</button></nav>
  <div class="scoreboard"></div></header>
  <p class="later" hidden></p>
  <main class="mode3" hidden><section class="m3-pane root-causes"></section>
    <section class="m3-pane event-impact"></section></main>
  <main class="workbench"><section class="pane queue"></section><section class="pane message"
    ></section><section class="pane context"></section></main>
  <script type="module" src="js/main.js"></script>
  <script>
    const errs = [];
    addEventListener("error", e => errs.push("ERR " + e.message));
    addEventListener("unhandledrejection", e => errs.push("REJ " + String(e.reason && e.reason.stack || e.reason)));
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    (async () => {
      for (let i = 0; i < 100 && document.querySelectorAll(".queue-row").length < 60; i++) await sleep(100);
      document.querySelector('button[data-mode="3"]').click();
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.event-impact .m3-table tbody tr"); i++) await sleep(200);
      await sleep(1500);
      const out = {
        errs,
        mode3Visible: !document.querySelector(".mode3").hidden,
        workbenchHidden: document.querySelector(".workbench").hidden,
        headline: (document.querySelector(".m3-headline") || {}).textContent || "",
        stats: [...document.querySelectorAll(".m3-stats .stat b")].map(b => b.textContent),
        bars: document.querySelectorAll(".m3-chart rect").length,
        cumLine: !!document.querySelector(".m3-chart polyline"),
        tableRows: document.querySelectorAll(".m3-pane.root-causes .m3-table tbody tr").length,
        topCause: (document.querySelector(".m3-pane.root-causes .m3-table tbody tr td") || {}).textContent || "",
        eventRows: document.querySelectorAll(".m3-pane.event-impact .m3-table tbody tr").length,
        topEvent: (document.querySelector(".m3-pane.event-impact .m3-table tbody tr td:nth-child(2)") || {})
          .textContent || "",
        quietTags: document.querySelectorAll(".m3-pane.event-impact .quiet").length
      };
      const pre = document.createElement("pre"); pre.id = "dbg";
      pre.textContent = JSON.stringify(out); pre.dataset.state = "done";
      document.body.appendChild(pre);
    })();
  </script>
</body></html>"""
PORT = 8823
probe = served / "__probe_mode3.html"
probe.write_text(HTML)
env = {**os.environ, "OVERHEARD_DB_PATH": str(db)}
log = open("/tmp/probe_mode3.log", "w")
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
    # NOTE: snap chromium's --screenshot vanishes into its private /tmp (its
    # stdout claims "written", the file is never here); use a real path instead.
    shot = str(Path(__file__).resolve().parent.parent / "probe_mode3_shot.png")
    res = subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--virtual-time-budget=25000", "--window-size=1400,900", f"--screenshot={shot}",
         "--dump-dom", f"http://127.0.0.1:{PORT}/__probe_mode3.html"],
        capture_output=True, text=True, timeout=180)
    print("chromium rc:", res.returncode, (res.stderr or "").strip()[-400:])
    m = re.search(r'<pre id="dbg"[^>]*>(.*?)</pre>', res.stdout, re.S)
    assert m, f"probe never finished; len(dom)={len(res.stdout)}"
    out = json.loads(m.group(1).replace("&amp;", "&"))
    print(json.dumps(out, indent=1))
    assert out["errs"] == [], out["errs"]
    assert out["mode3Visible"] and out["workbenchHidden"]
    assert out["topCause"].replace(" ", "").lower() == "form22bconfusion", out["topCause"]
    assert out["bars"] >= 12 and out["cumLine"]
    assert out["tableRows"] == 10
    assert out["eventRows"] == 14, out["eventRows"]
    assert "22-B" in out["topEvent"] and "1st mailing" in out["topEvent"], out["topEvent"]
    assert out["quietTags"] >= 1
    print("PROBE_MODE3 OK, screenshot at", shot)
finally:
    proc.kill()
    proc.wait()
    log.close()
    probe.unlink(missing_ok=True)
