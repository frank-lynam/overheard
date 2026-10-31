# Goal

Mode 3 view 10 (event-driven staffing forecast) live end to end: analytics module projecting call volume and agent hours for the next 14 days from the events calendar + measured baseline, GET route, mode-3 pane, tests, probe + screenshot, commit/push, board report.

## How it works

Views 1-9 of Mode 3 are built. Pattern: analytics module (plain code over the seeded archive) -> GET route in routes.py -> .m3-pane in index.html + render fn in mode3.js + lazy block in main.js + api.js entry + css -> pytest in tests/test_mode3.py -> ruff --no-fix -> full pytest -> extend tools/probe_mode3_ui.py + screenshot at a real repo path -> commit+push (announce) -> board comment + attach shot -> tick+PUT checklist. Archive = weekdays 2023-03-10..2026-03-09, today=2026-03-10 (meta). ~89 weekday baseline contacts, avg handle 5.19 min. EVENTS (data/events.py) carries (id, date, type, name, desc, driver, peak extra/day at start, days) — the generator decays excess as peak*exp(-3*age/days) scaled by VOLUME=6.75. The only event active at "today" is ev-payday-12 (2026-02-27, payment-date-shift, peak 6.0, 14 days -> ends 2026-03-12): its 3-day tail is the planted "upcoming" work. app.state.today exists; weak-signals route is the template for headline+prov.

## Why it doesn't

No staffing forecast exists: no analytics module, no /api/staffing-forecast route, no pane, no tests. DESIGN.md view 10: "Uses upcoming mailings and releases to project call volume and the agent hours needed."

## What would

analytics/staffing.py: per-day projection for the next 14 days from today: weekday baseline (mean contacts/day over the archive's trailing 90 weekdays) + event excess from the calendar's own decay curve (peak*exp(-3*age/days)*VOLUME) for every event active in the window; agent hours from measured mean handle minutes (global for baseline, per-driver for event excess). Card per active event: remaining days, predicted excess contacts and hours. GET /api/staffing-forecast with headline + prov. Pane .m3-pane.staffing-forecast + renderStaffingForecast + lazy block + api entry + css. Tests: 14 days, 10 weekdays, 4 weekends (zero baseline), payment-date-shift tail present with ~19 excess contacts and a few hours, steady days after the tail are pure baseline, API 200. Then ruff --no-fix, full pytest, extend probe + screenshot, commit+push (announce), board comment + shot, tick+PUT checklist.

## Steps

- [x] 1. 1. analytics/staffing.py: 14-day daily projection (weekday baseline + event decay excess), per-event cards with predicted excess contacts/hours, agent hours
- [x] 2. 2. GET /api/staffing-forecast route with headline + prov
- [x] 3. 3. Mode-3 pane: index.html + api.js + mode3.js renderStaffingForecast + main.js lazy block + css
- [x] 4. 4. pytest: day counts, payment-date tail excess ~19 contacts, steady baseline after, weekends zero-baseline, API 200
- [x] 5. 5. ruff --no-fix + full pytest green
- [x] 6. 6. extend chromium probe + screenshot (repo path)
- [x] 7. 7. commit + push (announce)
- [x] 8. 8. board comment + screenshot + PUT checklist 8/8
