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
    <section class="m3-pane event-impact"></section>
    <section class="m3-pane journeys"></section>
    <section class="m3-pane promises"></section>
    <section class="m3-pane equity"></section>
    <section class="m3-pane letter-lab"></section></main>
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
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.journeys .m3-table tbody tr"); i++) await sleep(200);
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.promises .m3-table tbody tr"); i++) await sleep(200);
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.equity .m3-table tbody tr"); i++) await sleep(200);
      // the letter lab: wait for its form, run a pre-test, wait for the results
      for (let i = 0; i < 100 && !document.querySelector(".m3-pane.letter-lab #ll-run"); i++) await sleep(200);
      const ll = document.querySelector(".m3-pane.letter-lab");
      document.querySelector(".m3-pane.letter-lab #ll-run").click();
      for (let i = 0; i < 150 && (ll.querySelector(".m3-letterlab-results") || {}).hidden; i++) await sleep(200);
      document.querySelector(".m3-pane.letter-lab").scrollIntoView();
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
        quietTags: document.querySelectorAll(".m3-pane.event-impact .quiet").length,
        journeyRows: document.querySelectorAll(".m3-pane.journeys .m3-table").length >= 2
          ? document.querySelectorAll(".m3-pane.journeys .m3-table:last-of-type tbody tr").length : 0,
        journeyCauseRows: document.querySelectorAll(".m3-pane.journeys .m3-table tbody tr").length,
        loopsStat: (document.querySelector(".m3-pane.journeys .m3-stats .stat b") || {}).textContent || "",
        journeyTopCause: (document.querySelector(".m3-pane.journeys .m3-table tbody tr td") || {}).textContent || "",
        journeyHeadline: (document.querySelector(".m3-pane.journeys .m3-headline") || {}).textContent || "",
        journeyProv: (document.querySelector(".m3-pane.journeys .prov") || {}).textContent || "",
        promiseRows: document.querySelectorAll(".m3-pane.promises .m3-table").length >= 2
          ? document.querySelectorAll(".m3-pane.promises .m3-table:first-of-type tbody tr").length : 0,
        promiseBars: document.querySelectorAll(".m3-pane.promises .m3-promise-row").length,
        promiseTopCause: (document.querySelector(".m3-pane.promises .m3-table:first-of-type tbody tr td") || {})
          .textContent || "",
        promiseHeadline: (document.querySelector(".m3-pane.promises .m3-headline") || {}).textContent || "",
        promiseProv: (document.querySelector(".m3-pane.promises .prov") || {}).textContent || "",
        equityRows: document.querySelectorAll(".m3-pane.equity .m3-table:first-of-type tbody tr").length,
        equityBars: document.querySelectorAll(".m3-pane.equity .m3-equity-row").length,
        equityTop: (document.querySelector(".m3-pane.equity .m3-table:first-of-type tbody tr td") || {})
          .textContent || "",
        equityHeadline: (document.querySelector(".m3-pane.equity .m3-headline") || {}).textContent || "",
        equityProv: (document.querySelector(".m3-pane.equity .prov") || {}).textContent || "",
        letterLabPane: !!document.querySelector(".m3-pane.letter-lab"),
        letterLabHeadline: (document.querySelector(".m3-pane.letter-lab .m3-letterlab-results .m3-headline") || {})
          .textContent || "",
        letterLabRewrite: (document.querySelector(".m3-pane.letter-lab .m3-letterlab-rewrite") || {}).textContent || "",
        letterLabQuestions: document.querySelectorAll(".m3-pane.letter-lab .m3-letterlab-questions li").length,
        letterLabProv: (document.querySelector(".m3-pane.letter-lab .prov") || {}).textContent || ""
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
         "--virtual-time-budget=25000", "--window-size=1400,3000", f"--screenshot={shot}",
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
    PLANTED = {"identity check hold", "appeal status", "overpayment notice", "form 22b confusion"}
    assert out["journeyRows"] == 10, out["journeyRows"]
    assert out["journeyCauseRows"] >= 4, out["journeyCauseRows"]
    assert int(out["loopsStat"].replace(",", "")) > 900, out["loopsStat"]
    assert out["journeyTopCause"].lower().strip() in PLANTED, out["journeyTopCause"]
    assert out["journeyTopCause"].lower().strip() in out["journeyHeadline"].lower()
    assert "plain code" in out["journeyProv"] and "journeys over the archive" in out["journeyProv"]
    assert out["promiseRows"] >= 10, out["promiseRows"]
    assert out["promiseBars"] >= 10, out["promiseBars"]
    assert out["promiseTopCause"].strip() == "appeal status", out["promiseTopCause"]
    assert "appeal status" in out["promiseHeadline"].lower()
    assert "plain code" in out["promiseProv"] and "promises vs. the archive" in out["promiseProv"]
    assert out["equityRows"] == 5, out["equityRows"]
    assert out["equityBars"] == 5, out["equityBars"]
    assert out["equityTop"].strip() == "vi", out["equityTop"]
    assert "vi" in out["equityHeadline"].lower(), out["equityHeadline"]
    assert "plain code" in out["equityProv"] and "contacts by language and channel" in out["equityProv"]
    assert out["letterLabPane"]
    assert "form 22-b" in out["letterLabHeadline"].lower(), out["letterLabHeadline"]
    assert "what to do" in out["letterLabRewrite"].lower()
    assert out["letterLabQuestions"] == 6
    assert "plain code" in out["letterLabProv"]
    print("PROBE_MODE3 OK, screenshot at", shot)
finally:
    proc.kill()
    proc.wait()
    log.close()
    probe.unlink(missing_ok=True)
