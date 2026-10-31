# Goal

Mode 3 view 9 (missed weak signals) live end to end: analytics module finding drivers that showed an elevated slow-burn BEFORE their spike event (how early they could have been caught), GET route, mode-3 pane, tests recovering the planted 1099 trickle-then-spike, probe + screenshot, commit/push, board report.

## How it works

View 8 done (commit 03fc391, 88 passed, probe OK, comment 158, shot 77, checklist 8/8). Planted weak signal is in events.py: ev-1099-quiet (policy 2024-10-01, peak 0.25 extra/day, 110 days, driver tax-form-1099) — a trickle — then ev-1099-spike (mailing 2025-01-27, peak 8.0, 20 days). contacts table has root_cause + at (ISO). Established pattern per view: analytics module -> GET route -> pane + render fn + lazy block + css -> pytest -> ruff --no-fix -> full pytest -> probe+shot -> commit/push -> board comment + attachment + checklist PUT.

## Why it doesn't

No analytics module scans for pre-spike slow-burns: events.py module only measures excess AROUND events, journeys/promises/equity/letter-lab/ask don't touch the question "how early could this have been caught?". No /api/weak-signals route, no pane, no tests.

## What would

analytics/weak_signals.py: for each driver, weekly contact series; baseline = median of that driver's weeks outside known event windows; scan the ~12 weeks before each major spike event for weeks above a multiple of baseline; a driver with a sustained early elevation (several weeks above) gets a card: the spike event, when the trickle started, how many weeks/months early a threshold alert would have fired, trickle size vs spike size. GET /api/weak-signals in routes.py. Pane .m3-pane.weak-signals + renderWeakSignals + lazy block + css. Tests: tax-form-1099 flagged with signal predating ev-1099-spike (and ev-1099-quiet the trigger), a driver with no pre-spike elevation NOT flagged, API 200. Ruff --no-fix, full pytest, extend probe + screenshot (repo path), commit+push (announce), board comment + shot, tick+PUT checklist.

## Steps

- [x] 1. 1. analytics/weak_signals.py (baseline per driver, pre-spike slow-burn scan, how-early estimate)
- [x] 2. 2. GET /api/weak-signals route
- [x] 3. 3. Mode-3 pane: index.html + api.js + mode3.js + main.js + css
- [x] 4. 4. pytest: 1099 trickle predates its spike, quiet event named, no-fake-flag, API 200
- [x] 5. 5. ruff --no-fix + full pytest green
- [x] 6. 6. extend chromium probe + screenshot
- [ ] 7. 7. commit + push (announce)
- [ ] 8. 8. board comment + screenshot + PUT checklist 8/8
