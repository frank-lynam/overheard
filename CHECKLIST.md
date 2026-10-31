# Goal

Mode 3 view 3 (caller journeys / repeat callers) is live end to end: analytics/journeys.py, GET /api/archive/journeys, mode-3 journeys pane, tests on the planted loops, chromium probe, pushed, reported on the board.

## How it works

Archive is pre-labeled: contacts(id, case_id, at, channel, root_cause, lang, region, handle_min, resolved, days_to_resolve, text, promise) — 71,788 rows across 25,000 case pools. The generator PLANTs loops: LOOP_SHARE=0.04 of callers get 3-6 'phone' contacts on one unresolved root cause (identity-check-hold, appeal-status, overpayment-notice, form-22b-confusion), never resolved; meta.loop_contacts records the planted count. Mode 3 already has view 1 (root-cause Pareto) and view 2 (event impact) panes.

## Why it doesn't

There is no journeys/repeat-caller view: analytics/ has only root_causes.py and events.py, no /api/archive/journeys route, and the mode-3 section of the UI has no journeys pane. The design (docs/DESIGN.md §Mode 3.3) asks for: callers stuck in loops (3+ contacts about one issue with no resolution) and the process steps where loops start.

## What would

New src/overheard/analytics/journeys.py: group contacts by (case_id, root_cause); a loop = 3+ contacts, latest contact unresolved; report loop count, loop contacts, hours, loops by starting cause, worst offenders (most contacts, longest duration), and compare loop detection against planted meta.loop_contacts. GET /api/archive/journeys in routes.py. Mode-3 journeys pane (hand-written HTML/CSS, no libs) with headline, loops-by-cause table, worst-loops list, provenance badge. Tests: planted loops recovered (detected loop contacts within a sane band of meta.loop_contacts, top starting cause in the planted set, completeness, API 200). Chromium probe asserts the pane; commit+push; board comment. Check: pytest green, ruff clean, probe OK, screenshot shows the pane.

## Steps

- [x] 1. analytics/journeys.py: repeat_callers(con) — loop detection, per-cause breakdown, worst loops, planted-band check
- [x] 2. API route GET /api/archive/journeys
- [x] 3. Mode-3 journeys pane: index.html section + js/ui/mode3.js render + css
- [x] 4. pytest: planted loops recovered (band vs meta.loop_contacts, top cause in planted set, API 200)
- [x] 5. ruff + full pytest green
- [x] 6. chromium probe: assert journeys pane + screenshot
- [x] 7. commit + push
- [x] 8. board comment with report + screenshot
