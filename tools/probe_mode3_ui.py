"""Throwaway mode-3 browser probe: boots the real app on a throwaway port with a
seeded throwaway db, loads the real js/css with a probe page, flips to mode 3,
clicks through the dashboard's ten archive-view tabs, checks the DOM of every
pane and the tab navigation, and saves screenshots."""

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
PANE_ORDER = [
    "root-causes", "event-impact", "journeys", "promises", "equity",
    "letter-lab", "ask", "knowledge-gaps", "weak-signals", "staffing-forecast",
]
HTML = """<html><head><meta charset="utf-8"></head><body>
  <header class="topbar"><nav class="stepper">
  <button data-mode="0" aria-pressed="true">0</button><button data-mode="1">1</button>
  <button data-mode="2">2</button><button data-mode="3">3</button></nav>
  <div class="scoreboard"></div></header>
  <p class="later" hidden></p>
  <main class="mode3" hidden><nav class="m3-tabs" role="tablist" aria-label="Archive views">
    <button class="m3-tab" role="tab" data-pane="root-causes" aria-selected="true">Root causes</button>
    <button class="m3-tab" role="tab" data-pane="event-impact">Events</button>
    <button class="m3-tab" role="tab" data-pane="journeys">Journeys</button>
    <button class="m3-tab" role="tab" data-pane="promises">Promises</button>
    <button class="m3-tab" role="tab" data-pane="equity">Equity</button>
    <button class="m3-tab" role="tab" data-pane="letter-lab">Letter lab</button>
    <button class="m3-tab" role="tab" data-pane="ask">Ask</button>
    <button class="m3-tab" role="tab" data-pane="knowledge-gaps">Knowledge gaps</button>
    <button class="m3-tab" role="tab" data-pane="weak-signals">Weak signals</button>
    <button class="m3-tab" role="tab" data-pane="staffing-forecast">Staffing</button>
  </nav>
    <section class="m3-pane root-causes" role="tabpanel" data-pane="root-causes" aria-label="Root causes"></section>
    <section class="m3-pane event-impact" role="tabpanel" data-pane="event-impact" aria-label="Events" hidden></section>
    <section class="m3-pane journeys" role="tabpanel" data-pane="journeys" aria-label="Journeys" hidden></section>
    <section class="m3-pane promises" role="tabpanel" data-pane="promises" aria-label="Promises" hidden></section>
    <section class="m3-pane equity" role="tabpanel" data-pane="equity" aria-label="Equity" hidden></section>
    <section class="m3-pane letter-lab" role="tabpanel" data-pane="letter-lab" aria-label="Letter lab" hidden></section>
    <section class="m3-pane ask" role="tabpanel" data-pane="ask" aria-label="Ask the archive"
      hidden></section>
    <section class="m3-pane knowledge-gaps" role="tabpanel" data-pane="knowledge-gaps"
      aria-label="Knowledge gaps" hidden></section>
    <section class="m3-pane weak-signals" role="tabpanel" data-pane="weak-signals"
      aria-label="Weak signals" hidden></section>
    <section class="m3-pane staffing-forecast" role="tabpanel" data-pane="staffing-forecast"
      aria-label="Staffing forecast" hidden></section>
  </main>
  <main class="workbench"><section class="pane queue"></section><section class="pane message"
    ></section><section class="pane context"></section></main>
  <script type="module" src="js/main.js"></script>
  <script>
    const errs = [];
    addEventListener("error", e => errs.push("ERR " + e.message));
    addEventListener("unhandledrejection", e => errs.push("REJ " + String(e.reason && e.reason.stack || e.reason)));
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const sel = s => document.querySelector(s);
    const all = s => [...document.querySelectorAll(s)];
    const wait = async (cond, n = 150) => {
      for (let i = 0; i < n; i++) { if (cond()) return; await sleep(200); }
    };
    (async () => {
      for (let i = 0; i < 100 && all(".queue-row").length < 60; i++) await sleep(100);
      sel('button[data-mode="3"]').click();
      await wait(() => sel(".m3-pane.root-causes .m3-table tbody tr"));
      // click through every tab, waiting for its content on the way
      for (const name of ["event-impact", "journeys", "promises", "equity", "letter-lab",
          "ask", "knowledge-gaps", "weak-signals", "staffing-forecast"]) {
        sel(`.m3-tab[data-pane="${name}"]`).click();
        if (name === "letter-lab") {
          await wait(() => sel(".m3-pane.letter-lab #ll-run"));
          sel(".m3-pane.letter-lab #ll-run").click();
          await wait(() => !sel(".m3-pane.letter-lab .m3-letterlab-results").hidden);
        }
        if (name === "ask") {
          await wait(() => sel(".m3-pane.ask #ask-run"));
          sel(".m3-pane.ask #ask-sample").click();
          await wait(() => !sel(".m3-pane.ask .m3-ask-results").hidden);
        }
        await wait(() => {
          const pane = sel(`.m3-pane[data-pane="${name}"]`);
          if (name === "event-impact") return pane.querySelector(".m3-table tbody tr");
          if (name === "journeys") return pane.querySelector(".m3-table tbody tr");
          if (name === "promises") return pane.querySelector(".m3-table tbody tr");
          if (name === "equity") return pane.querySelector(".m3-table tbody tr");
          if (name === "knowledge-gaps") return pane.querySelector(".m3-kg-row");
          if (name === "weak-signals") return pane.querySelector(".m3-ws-card");
          if (name === "staffing-forecast") return pane.querySelector(".m3-sf-table");
          return pane.querySelector(".m3-head");
        });
      }
      // nav bookkeeping: exactly one pane visible, its tab aria-selected, the rest hidden
      const navAfter = {
        visiblePanes: all(".m3-pane").filter(p => !p.hidden).map(p => p.dataset.pane),
        selectedTabs: all(".m3-tab[aria-selected='true']").map(t => t.dataset.pane),
        hiddenPanes: all(".m3-pane[hidden]").length,
        tabCount: all(".m3-tab").length,
        panelRoles: all("[role='tabpanel']").length
      };
      const out = {
        errs, nav: navAfter,
        mode3Visible: !sel(".mode3").hidden,
        workbenchHidden: sel(".workbench").hidden,
        headline: (sel(".m3-headline") || {}).textContent || "",
        stats: all(".m3-stats .stat b").map(b => b.textContent),
        bars: document.querySelectorAll(".m3-chart rect").length,
        cumLine: !!sel(".m3-chart polyline"),
        tableRows: document.querySelectorAll(".m3-pane.root-causes .m3-table tbody tr").length,
        topCause: (sel(".m3-pane.root-causes .m3-table tbody tr td") || {}).textContent || "",
        eventRows: document.querySelectorAll(".m3-pane.event-impact .m3-table tbody tr").length,
        topEvent: (sel(".m3-pane.event-impact .m3-table tbody tr td:nth-child(2)") || {})
          .textContent || "",
        quietTags: document.querySelectorAll(".m3-pane.event-impact .quiet").length,
        journeyRows: document.querySelectorAll(".m3-pane.journeys .m3-table").length >= 2
          ? document.querySelectorAll(".m3-pane.journeys .m3-table:last-of-type tbody tr").length : 0,
        journeyCauseRows: document.querySelectorAll(".m3-pane.journeys .m3-table tbody tr").length,
        loopsStat: (sel(".m3-pane.journeys .m3-stats .stat b") || {}).textContent || "",
        journeyTopCause: (sel(".m3-pane.journeys .m3-table tbody tr td") || {}).textContent || "",
        journeyHeadline: (sel(".m3-pane.journeys .m3-headline") || {}).textContent || "",
        journeyProv: (sel(".m3-pane.journeys .prov") || {}).textContent || "",
        promiseRows: document.querySelectorAll(".m3-pane.promises .m3-table").length >= 2
          ? document.querySelectorAll(".m3-pane.promises .m3-table:first-of-type tbody tr").length : 0,
        promiseBars: document.querySelectorAll(".m3-pane.promises .m3-bar-row").length,
        promiseTopCause: (sel(".m3-pane.promises .m3-table:first-of-type tbody tr td") || {})
          .textContent || "",
        promiseHeadline: (sel(".m3-pane.promises .m3-headline") || {}).textContent || "",
        promiseProv: (sel(".m3-pane.promises .prov") || {}).textContent || "",
        equityRows: document.querySelectorAll(".m3-pane.equity .m3-table:first-of-type tbody tr").length,
        equityBars: document.querySelectorAll(".m3-pane.equity .m3-bar-row").length,
        equityTop: (sel(".m3-pane.equity .m3-table:first-of-type tbody tr td") || {})
          .textContent || "",
        equityHeadline: (sel(".m3-pane.equity .m3-headline") || {}).textContent || "",
        equityProv: (sel(".m3-pane.equity .prov") || {}).textContent || "",
        letterLabPane: !!sel(".m3-pane.letter-lab"),
        letterLabHeadline: (sel(".m3-pane.letter-lab .m3-letterlab-results .m3-headline") || {})
          .textContent || "",
        letterLabRewrite: (sel(".m3-pane.letter-lab .m3-letterlab-rewrite") || {}).textContent || "",
        letterLabQuestions: document.querySelectorAll(".m3-pane.letter-lab .m3-letterlab-questions li").length,
        letterLabProv: (sel(".m3-pane.letter-lab .prov") || {}).textContent || "",
        askPane: !!sel(".m3-pane.ask"),
        askHeadline: (sel(".m3-pane.ask .m3-ask-results .m3-headline") || {}).textContent || "",
        askEvents: all(".m3-pane.ask .m3-ask-events li").map(li => li.textContent),
        askEvidence: document.querySelectorAll(".m3-pane.ask .m3-ask-evidence li").length,
        askProv: (sel(".m3-pane.ask .prov") || {}).textContent || "",
        kgPane: !!sel(".m3-pane.knowledge-gaps .m3-kg-gaps"),
        kgHeadline: (sel(".m3-pane.knowledge-gaps .m3-headline") || {}).textContent || "",
        kgRows: document.querySelectorAll(".m3-pane.knowledge-gaps .m3-kg-row").length,
        kgTopGap: (sel(".m3-pane.knowledge-gaps .m3-kg-gap") || {}).textContent || "",
        kgFaq: (sel(".m3-pane.knowledge-gaps .m3-kg-faq b") || {}).textContent || "",
        kgIvr: (sel(".m3-pane.knowledge-gaps .m3-kg-ivr") || {}).textContent || "",
        kgWeak: document.querySelectorAll(".m3-pane.knowledge-gaps .m3-kg-weak").length,
        kgFax: all(".m3-pane.knowledge-gaps .m3-kg-weak")
          .map(w => w.textContent).find(t => t.includes("Sending documents")) || "",
        kgProv: (sel(".m3-pane.knowledge-gaps .prov") || {}).textContent || "",
        wsPane: !!sel(".m3-pane.weak-signals .m3-ws-cards"),
        wsHeadline: (sel(".m3-pane.weak-signals .m3-headline") || {}).textContent || "",
        wsCards: document.querySelectorAll(".m3-pane.weak-signals .m3-ws-card").length,
        wsTopTitle: (sel(".m3-pane.weak-signals .m3-ws-card .m3-ws-title b") || {}).textContent || "",
        wsEarly: all(".m3-pane.weak-signals .m3-ws-card b")
          .map(b => b.textContent).find(t => /months early/.test(t)) || "",
        wsTrig: (sel(".m3-pane.weak-signals .m3-ws-card p:last-of-type") || {}).textContent || "",
        wsProv: (sel(".m3-pane.weak-signals .prov") || {}).textContent || "",
        sfPane: !!sel(".m3-pane.staffing-forecast .m3-sf-table"),
        sfHeadline: (sel(".m3-pane.staffing-forecast .m3-headline") || {}).textContent || "",
        sfDays: document.querySelectorAll(".m3-pane.staffing-forecast .m3-sf-table tbody tr").length,
        sfEventCards: document.querySelectorAll(".m3-pane.staffing-forecast .m3-sf-card").length,
        sfEventTitle: (sel(
          ".m3-pane.staffing-forecast .m3-sf-card .m3-sf-title b") || {}).textContent || "",
        sfProv: (sel(".m3-pane.staffing-forecast .prov") || {}).textContent || ""
      };
      // back to root-causes for the screenshot
      sel('.m3-tab[data-pane="root-causes"]').click();
      await sleep(500);
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
    stdout=log, stderr=subprocess.STDOUT, cwd=str(Path(__file__).resolve().parent.parent), env=env)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    # NOTE: snap chromium's --screenshot vanishes into its private /tmp (its
    # stdout claims "written", the file is never here); use a real path instead.
    shots = {
        "root-causes": str(Path(__file__).resolve().parent.parent / "probe_mode3_rootcauses.png"),
        "promises": str(Path(__file__).resolve().parent.parent / "probe_mode3_promises.png"),
    }
    for name, shot in shots.items():
        # the root-causes shot uses the full run (which ends back on root causes);
        # the others use a page that jumps straight to the tab before settling
        if name != "root-causes":
            html = HTML.replace(
                '      // click through every tab',
                f'      sel(`.m3-tab[data-pane="{name}"]`).click();\n'
                f'      await wait(() => sel(`.m3-pane[data-pane="{name}"] .m3-head`));\n'
                "      return;\n      // click through every tab",
                1,
            )
            probe.write_text(html)
        res = subprocess.run(
            ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
             "--virtual-time-budget=30000", "--window-size=1400,2000", f"--screenshot={shot}",
             f"http://127.0.0.1:{PORT}/__probe_mode3.html"],
            capture_output=True, text=True, timeout=180)
        if name != "root-causes":
            probe.write_text(HTML)
    print("chromium rc:", res.returncode, (res.stderr or "").strip()[-400:])
    # full DOM run for the assertions
    probe.write_text(HTML)
    res = subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--virtual-time-budget=45000", "--window-size=1400,2000", "--dump-dom",
         f"http://127.0.0.1:{PORT}/__probe_mode3.html"],
        capture_output=True, text=True, timeout=240)
    m = re.search(r'<pre id="dbg"[^>]*>(.*?)</pre>', res.stdout, re.S)
    assert m, f"probe never finished; len(dom)={len(res.stdout)}"
    out = json.loads(m.group(1).replace("&amp;", "&"))
    print(json.dumps(out, indent=1))
    assert out["errs"] == [], out["errs"]
    assert out["mode3Visible"] and out["workbenchHidden"]
    # the tab navigation itself
    nav = out["nav"]
    assert nav["tabCount"] == 10 and nav["panelRoles"] == 10, nav
    assert nav["visiblePanes"] == ["staffing-forecast"], nav
    assert nav["selectedTabs"] == ["staffing-forecast"], nav
    assert nav["hiddenPanes"] == 9, nav
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
    for shot in shots.values():
        assert Path(shot).stat().st_size > 5000, shot
    print("PROBE_MODE3 OK, screenshots at", ", ".join(shots.values()))
finally:
    proc.kill()
    proc.wait()
    log.close()
    probe.unlink(missing_ok=True)
