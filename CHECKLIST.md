# Goal

Mode 3 view 1 (root-cause Pareto) is live end to end: analytics module, API endpoint, dashboard UI with SVG Pareto, tests, ruff, chromium probe, pushed, reported on the board.

## How it works

Archive is pre-labeled: contacts(root_cause, handle_min, resolved, region, lang, at) — 71,788 contacts in /tmp/oh.db, verified form-22b-confusion tops hours (717.7h, 11.6% share). No analytics/ dir or archive API exists yet; static/ has mode stepper (Mode 3 currently shows 'arrives in a later build').

## Why it doesn't

-

## What would

New analytics/root_causes.py (SQL aggregates + cost model with configurable labor rate), /api/archive/root-causes endpoint, Mode-3 dashboard section + hand-written SVG Pareto chart in js/charts/, pytest assertions on rank-1 identity and share within 10% of measured baseline, browser probe + screenshot.

## Steps

- [x] 1. analytics/root_causes.py with cost model + config labor rate
- [x] 2. API route /api/archive/root-causes
- [x] 3. Mode-3 dashboard UI + SVG Pareto chart
- [x] 4. pytest: rank 1 = form-22b-confusion, shares stable
- [x] 5. ruff + full pytest green
- [x] 6. chromium probe + screenshot
- [ ] 7. commit + push
- [ ] 8. board comment
