# Goal

Mode 0 complete end-to-end per the build order: UI pieces verified working in a real browser, workload-clock extrapolation visible and editable, tests green, pushed to ticket/fancy-wombat, reported on the board.

## How it works

Read ui/queue.js, ui/message.js, ui/context.js, ui/scoreboard.js, core/store.js, core/api.js, format.js, simulate.py, cli.py, tests/test_mode0.py, app.py. All Mode 0 design pieces exist: arrival-ordered inbox, speaking-pace (~150 wpm) transcript reveal, manual entry form (all design fields), effort timer, case lookup, "work the queue" simulation, scoreboard v1. Simulation math: listen at speed + handleMin (3.5, editable via API) + callbackMin (6) per message.

## Why it doesn't

Gaps: (1) DESIGN says "measured effort: real time per message, plus configurable handling time (3.5 min default) that extrapolates the workload clock" — handleMin is editable via API but nothing in the UI exposes it, and the workload clock only appears after clicking "work the queue"; (2) no end-to-end test that the browser UI renders and works at all.

## What would

(1) message.js: show per-message workload clock (listen + handling + callback, from /api/assumptions). (2) scoreboard.js: always-visible extrapolated workload-clock stat with an editable handling time. (3) tests/test_mode0_ui.py: structural tests (index.html/JS contain the required Mode 0 pieces) + real headless-Chromium smoke test against a live server (queue renders, work-the-queue fills the scoreboard). (4) ruff+pytest green, screenshots of the modes, push, board comment + checklist upload.

## Steps

- [x] 1. Edit ui/message.js: per-message workload clock from assumptions
- [x] 2. Edit ui/scoreboard.js: always-visible extrapolation + editable handling time
- [x] 3. Add tests/test_mode0_ui.py (structural + Chromium smoke)
- [ ] 4. Run ruff + pytest, serve + screenshots (mode 0 before/after sim)
- [ ] 5. Push to deploy; tick steps 1-2, post comment, upload checklist, update MEMORY
