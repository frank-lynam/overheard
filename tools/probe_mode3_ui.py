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
    <section class="m3-pane letter-lab"></section>
    <section class="m3-pane ask"></section>
    <section class="m3-pane knowledge-gaps"></section>
    <section class="m3-pane weak-signals"></section>
    <section class="m3-pane staffing-forecast"></section></main>
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
      // the ask pane: wait for its form, run the sample question, wait for the answer
      for (let i = 0; i < 100 && !document.querySelector(".m3-pane.ask #ask-run"); i++) await sleep(200);
      const askp = document.querySelector(".m3-pane.ask");
      document.querySelector(".m3-pane.ask #ask-sample").click();
      for (let i = 0; i < 150 && (askp.querySelector(".m3-ask-results") || {}).hidden; i++) await sleep(200);
      askp.scrollIntoView();
      await sleep(1000);
      // the knowledge-gaps pane: wait for its rows (fetched from /api/knowledge-gaps)
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.knowledge-gaps .m3-kg-row"); i++) await sleep(200);
      document.querySelector(".m3-pane.knowledge-gaps").scrollIntoView();
      await sleep(1000);
      // the weak-signals pane: wait for its cards (fetched from /api/weak-signals)
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.weak-signals .m3-ws-card"); i++) await sleep(200);
      document.querySelector(".m3-pane.weak-signals").scrollIntoView();
      await sleep(1000);
      // the staffing-forecast pane: wait for its day-by-day table (fetched from /api/staffing-forecast)
      for (let i = 0; i < 150 && !document.querySelector(".m3-pane.staffing-forecast .m3-sf-table"); i++) await sleep(200);
      document.querySelector(".m3-pane.staffing-forecast").scrollIntoView();
      await sleep(1000);
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
        letterLabProv: (document.querySelector(".m3-pane.letter-lab .prov") || {}).textContent || "",
        askPane: !!document.querySelector(".m3-pane.ask"),
        askHeadline: (document.querySelector(".m3-pane.ask .m3-ask-results .m3-headline") || {}).textContent || "",
        askEvents: [...document.querySelectorAll(".m3-pane.ask .m3-ask-events li")].map(li => li.textContent),
        askEvidence: document.querySelectorAll(".m3-pane.ask .m3-ask-evidence li").length,
        askProv: (document.querySelector(".m3-pane.ask .prov") || {}).textContent || "",
        kgPane: !!document.querySelector(".m3-pane.knowledge-gaps .m3-kg-gaps"),
        kgHeadline: (document.querySelector(".m3-pane.knowledge-gaps .m3-headline") || {}).textContent || "",
        kgRows: document.querySelectorAll(".m3-pane.knowledge-gaps .m3-kg-row").length,
        kgTopGap: (document.querySelector(".m3-pane.knowledge-gaps .m3-kg-gap") || {}).textContent || "",
        kgFaq: (document.querySelector(".m3-pane.knowledge-gaps .m3-kg-faq b") || {}).textContent || "",
        kgIvr: (document.querySelector(".m3-pane.knowledge-gaps .m3-kg-ivr") || {}).textContent || "",
        kgWeak: document.querySelectorAll(".m3-pane.knowledge-gaps .m3-kg-weak").length,
        kgFax: [...document.querySelectorAll(".m3-pane.knowledge-gaps .m3-kg-weak")]
          .map(w => w.textContent).find(t => t.includes("Sending documents")) || "",
        kgProv: (document.querySelector(".m3-pane.knowledge-gaps .prov") || {}).textContent || "",
        wsPane: !!document.querySelector(".m3-pane.weak-signals .m3-ws-cards"),
        wsHeadline: (document.querySelector(".m3-pane.weak-signals .m3-headline") || {}).textContent || "",
        wsCards: document.querySelectorAll(".m3-pane.weak-signals .m3-ws-card").length,
        wsTopTitle: (document.querySelector(".m3-pane.weak-signals .m3-ws-card .m3-ws-title b") || {}).textContent || "",
        wsEarly: [...document.querySelectorAll(".m3-pane.weak-signals .m3-ws-card b")]
          .map(b => b.textContent).find(t => /months early/.test(t)) || "",
        wsTrig: (document.querySelector(".m3-pane.weak-signals .m3-ws-card p:last-of-type") || {}).textContent || "",
        wsProv: (document.querySelector(".m3-pane.weak-signals .prov") || {}).textContent || "",
        sfPane: !!document.querySelector(".m3-pane.staffing-forecast .m3-sf-table"),
        sfHeadline: (document.querySelector(".m3-pane.staffing-forecast .m3-headline") || {}).textContent || "",
        sfDays: document.querySelectorAll(".m3-pane.staffing-forecast .m3-sf-table tbody tr").length,
        sfEventCards: document.querySelectorAll(".m3-pane.staffing-forecast .m3-sf-card").length,
        sfEventTitle: (document.querySelector(".m3-pane.staffing-forecast .m3-sf-card .m3-sf-title b") || {}).textContent || "",
        sfProv: (document.querySelector(".m3-pane.staffing-forecast .prov") || {}).textContent || ""
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
         "--virtual-time-budget=30000", "--window-size=1400,6200", f"--screenshot={shot}",
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
    assert out["askPane"]
    assert "22-b" in out["askHeadline"].lower(), out["askHeadline"]
    assert "ev-22b-3" not in out["askHeadline"] and any("3rd mailing" in e for e in out["askEvents"]), out["askEvents"]
    assert out["askEvidence"] >= 1
    assert "plain code" in out["askProv"] and "totals over the archive" in out["askProv"]
    assert out["kgPane"] and out["kgRows"] >= 5, out["kgRows"]
    assert "form 22b" in out["kgTopGap"].lower(), out["kgTopGap"]
    assert "22-B" in out["kgFaq"], out["kgFaq"]
    assert "for help with this topic from the" in out["kgIvr"], out["kgIvr"]
    assert out["kgWeak"] >= 4, out["kgWeak"]
    assert "Sending documents" in out["kgFax"] and "fax" in out["kgFax"].lower(), out["kgFax"]
    assert "kb_articles against the archive" in out["kgProv"], out["kgProv"]
    assert "topics covered" in out["kgHeadline"], out["kgHeadline"]
    assert out["wsPane"], "weak-signals pane not rendered"
    assert out["wsCards"] >= 1, out["wsCards"]
    assert "1099" in out["wsTopTitle"], out["wsTopTitle"]
    assert "early" in out["wsEarly"].lower(), out["wsEarly"]
    assert "1099" in out["wsHeadline"].lower(), out["wsHeadline"]
    assert "vendor change" in out["wsTrig"].lower(), out["wsTrig"]
    assert "plain code" in out["wsProv"] and "weekly totals" in out["wsProv"], out["wsProv"]
    assert out["sfPane"], "staffing-forecast pane not rendered"
    assert out["sfDays"] == 14, out["sfDays"]
    assert out["sfEventCards"] == 1, out["sfEventCards"]
    assert "Payment date" in out["sfEventTitle"], out["sfEventTitle"]
    assert "payment-date-shift" in out["sfHeadline"], out["sfHeadline"]
    assert "plain code" in out["sfProv"], out["sfProv"]
    print("PROBE_MODE3 OK, screenshot at", shot)
finally:
    proc.kill()
    proc.wait()
    log.close()
    probe.unlink(missing_ok=True)
