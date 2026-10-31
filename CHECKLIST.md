# Goal

Mode 3 view 4 (promises vs. outcomes) is live end to end: broken-promise rates by issue type and team, with the planted BROKEN rates (appeal 62%, claim 35%, identity 45%) recovered by the tests.

## How it works

generator.py plants promise JSON in ~30% of contacts: kept=null past archive end, kept=false at per-cause rates from the BROKEN dict (appeal-status 0.62, claim-status 0.35, identity-check-hold 0.45, default 0.08). Everything needed is in contacts.promise + root_cause + cases.team (all 'general' in the archive).

## Why it doesn't

No analytics/promises.py, no /api/archive/promises route, no UI pane, no tests: the promise column is unexamined.

## What would

New src/overheard/analytics/promises.py: parse promise JSON, bucket kept/broken/not-yet-due per root cause and per team, broken rate within settled promises, worst-cause offenders, share of contacts broken-kept. GET /api/archive/promises in api/routes.py. Mode-3 promises pane (hand-written HTML/CSS). Tests: planted rates within ~5pts band, completeness (kept+broken+pending == total promise contacts), default-rate causes near 0.08, API 200. Chromium probe asserts the pane; commit+push; board comment. Check: pytest green, ruff clean, probe OK, screenshot shows the pane.

## Steps

- [x] 1. analytics/promises.py: promise_outcomes(con) — kept/broken/pending per cause + per team, totals
- [x] 2. API route GET /api/archive/promises
- [x] 3. Mode-3 promises pane: index.html section + js/ui/mode3.js renderPromises
- [x] 4. pytest: planted broken rates recovered within band, completeness, API 200
- [x] 5. ruff + full pytest green
- [x] 6. chromium probe: assert promises pane + screenshot
- [x] 7. commit + push
- [x] 8. board comment with report + screenshot
