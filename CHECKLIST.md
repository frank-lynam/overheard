# Goal

Mode 3 view 2 (event impact) is live end to end: analytics/events.py, /api/archive/event-impact, mode-3 event pane, tests on the planted signals, chromium probe, pushed, reported on the board.

## How it works

Seeded archive plants signals in data/events.py: each event adds Poisson excess contacts for one root_cause (driver), peaking at start and fading over `days` (lam += peak*exp(-3*age/days), scaled by VOLUME=6.75). DB events table has id/date/type/name/description; driver/peak/days live in the EVENTS tuples (calendar metadata) — analytics can join by id. Expected recoveries: 22-B mailings top the excess list (~1000 each), ev-portal-42 release ~600, ev-1099-quiet vendor change a sliver.

## Why it doesn't

Only view 1 exists: no analytics/events.py, no /api/archive/event-impact route, no event pane in index.html/mode3.js, no tests for it.

## What would

New src/overheard/analytics/events.py (per-event window contacts/hours vs own-cause weekday baseline, excess, share), GET /api/archive/event-impact, mode-3 event-impact pane (hand-written HTML/CSS sorted by excess), pytest asserting planted signals (22-B mailing rank 1, portal-42 top-3, 1099-quiet near bottom, completeness), chromium probe asserts the new pane, commit+push, board comment. Check: pytest green, ruff clean, probe OK, screenshot shows the pane.

## Steps

- [x] 1. analytics/events.py: event_impact(con) — window stats, baseline, excess, hours, shares
- [x] 2. API route GET /api/archive/event-impact
- [x] 3. Mode-3 event-impact pane: index.html section + js/ui/mode3.js render + css
- [x] 4. pytest: planted signals recovered (22-B top, portal-42 top-3, 1099-quiet bottom, all 14 events present)
- [x] 5. ruff + full pytest green
- [x] 6. chromium probe: assert event pane + screenshot
- [ ] 7. commit + push
- [ ] 8. board comment with report + screenshot
