"""Mode-1 screenshot: boots the real app on a throwaway port with a seeded throwaway
db, opens the real index.html in headless chromium, switches to mode 1, opens the
top (most urgent) row, and saves a full-page-height screenshot."""

import os
import subprocess
import time
import urllib.request
from importlib.resources import files
from pathlib import Path

from overheard.data.generator import seed

db = Path("/tmp/shot-mode1.db")
db.unlink(missing_ok=True)
seed(db, 2026)  # seed BEFORE the server boots: it takes its date and rows from the file
served = Path(files("overheard") / "static")
# A loader page: the real app's markup with a driver that flips to mode 1 and opens m37.
LOADER = """<html><head><meta charset="utf-8"></head>
<body data-mode="1">
  <header class="topbar">
    <div class="brand">Overheard <span class="agency">Federal Benefits Service Center · voicemail</span></div>
    <nav class="stepper" aria-label="AI mode">
      <button data-mode="0"><b>0</b> No AI</button>
      <button data-mode="1" aria-pressed="true"><b>1</b> Obvious AI</button>
      <button data-mode="2"><b>2</b> Non-obvious AI</button>
      <button data-mode="3"><b>3</b> Impossible without AI</button>
    </nav>
    <div class="scoreboard" aria-live="polite"><span class="muted">scoreboard</span></div>
  </header>
  <p class="later" hidden></p>
  <main class="workbench">
    <section class="pane queue"></section>
    <section class="pane message"><p class="muted">Pick a message.</p></section>
    <section class="pane context"></section>
  </main>
  <script type="module" src="js/main.js"></script>
  <script>
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    (async () => {
      for (let i = 0; i < 100 && document.querySelectorAll(".queue-row").length < 60; i++) await sleep(50);
      const top = document.querySelector('.queue-row[data-id="m37"]') || document.querySelector(".queue-row");
      top && top.click();
      for (let i = 0; i < 200 && !document.querySelector(".ai-panel"); i++) await sleep(100);
      await sleep(1500); // let the accuracy stat land
      document.title = "shot-ready";
    })();
  </script>
</body></html>"""
loader = served / "__shot1.html"
loader.write_text(LOADER)
PORT = 8815
env = {**os.environ, "OVERHEARD_DB_PATH": str(db)}
log = open("/tmp/shot1.log", "w")
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
    out = Path("/home/bob/work/tickets/fancy-wombat/mode1.png")
    subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--window-size=1500,2400", "--virtual-time-budget=40000",
         f"--screenshot={out}", f"http://127.0.0.1:{PORT}/__shot1.html"],
        capture_output=True, text=True, timeout=300)
    print("saved", out, out.stat().st_size, "bytes")
finally:
    proc.terminate()
    proc.wait(timeout=10)
    loader.unlink(missing_ok=True)
    log.close()
