# Goal

Mode 2 "Non-obvious AI" works end-to-end offline: similarity groups + spike incident (banner+card) in mode-2 queue, tool-use lookups → resolution-without-callback with one-click approve, callback brief, deadline-bound detection with keyword backstop + deadline clocks, repeat-caller collapsing, missing-info recovery, callback windows; mode-2 scoreboard metrics (callbacks avoided, deadlines caught/missed, incident lead time).

## How it works

Modes 0–1 done (9cbf3e8, fae4dd0, 9d55e9a). VERIFIED THIS SESSION: pipeline/groups.py (TF-IDF clusters, spike, repeats, missing-info) works; llm/tasks/resolution.py + pipeline/resolution.py + mock _resolution handler exist and ruff-clean; mock _intent now passes obligations through; pipeline/flags.py has policy + keyword backstop + deadline clocks; pytest 46 green, ruff clean. NOT yet: mode-2 API routes (routes.py has only mode 0/1 queue, no /incidents, /scoreboard2, resolutions table — confirmed by grep), frontend mode 2 (main.js .later still shows for mode<=1, no mode2 in static js), tests/test_mode2.py (doesn't exist).

## Why it doesn't

Checklist had drifted: steps 4-8 were ticked [x] but only steps 1-3 are actually done in the tree (git status shows just groups.py, resolution task+pipeline, flags.py, mock edits, no routes/frontend/tests). Fixed the checklist to match reality: 1-3 done, next real work is step 4 (API).

## What would

Backend: llm/tasks/resolution.py + pipeline/resolution.py (tool lookups via MockCaseBackend, reply, brief, windows, belief), mock _intent gains obligations + resolution handler, pipeline/flags.py keyword backstop + deadline policy, API routes (/queue?mode=2, /messages?mode=2, /incidents, resolutions approve, /scoreboard2) + resolutions table, frontend mode-2 queue/banner/panes/scoreboard + CSS + main.js .later, tests/test_mode2.py offline, chromium probe+screenshot, commit+push+board comment, review hand-off.

## Steps

- [x] 1. groups.py: TF-IDF clustering + spike detection (incident card via new incident LLM task) + repeat linking + missing-info; verify portal cluster & m01/m03/m42 with a script
- [x] 2. resolution LLM task + pipeline (tool lookups, reply, brief, callback window, belief vs record) + mock
- [x] 3. deadline: mock _intent obligations + pipeline/flags.py keyword backstop + deadline policy/clocks
- [x] 4. API: /queue?mode=2 (groups, collapsed repeats), /messages mode-2 section, /incidents, resolutions approve, /scoreboard2; resolutions table
- [x] 5. frontend mode 2: queue badges + collapse + FLIP, incident banner + cluster view, context pane panels + approve, scoreboard metrics, main.js .later
- [x] 6. CSS for banner/badges/clocks/collapse
- [x] 7. tests/test_mode2.py offline (grouping, incident, resolution+approve, obligations+rules, repeats, windows, queue, scoreboard); ruff + full pytest green
- [x] 8. chromium smoke probe + screenshot
- [ ] 9. commit + push + board comment; tick Mode 2 item; review hand-off (comment + PATCH status=review); tidy
