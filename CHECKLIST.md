# Goal

Mode 3 view 5 (equity) is live end to end: wait times and outcomes by language and channel, showing Vietnamese callers wait ~1.35x longer and take ~2x longer to resolve (the planted SLOW_LANG="vi"), with tests recovering the planted gap.

## How it works

generator.py line 23 plants SLOW_LANG="vi"; per contact, slow-language callers get handle time ~gauss(1.35x, 0.25x) and resolution probability -0.15, and days_to_resolve doubled (line 113-116). Contacts carry lang and channel columns. Verified on a seeded db: vi avg wait 6.71 min vs zh 5.08 (1.32x), resolve rate 71.8% vs ~86%, days 31 vs ~15.

## Why it doesn't

No analytics/equity.py, no /api/archive/equity route, no equity UI pane, no tests for the language/channel gap: the planted SLOW_LANG signal is unexamined.

## What would

src/overheard/analytics/equity.py: per language and per channel — contact count, mean/median wait, resolution rate, mean days-to-resolve; worstLanguage/worstChannel with the wait ratio and the resolution gap. GET /api/archive/equity. Mode-3 equity pane (hand-written HTML/CSS: bars + two tables). Tests: vi is the slowest language, waitRatio within band of the planted 1.35, resolve-rate gap ~0.15, days ~2x; completeness vs raw SQL; API 200. Chromium probe asserts the pane; commit+push; board comment.

## Steps

- [x] 1. analytics/equity.py (DONE)
- [x] 2. API route GET /api/archive/equity (DONE)
- [x] 3. Mode-3 equity pane: index.html + main.js + mode3.js renderEquity + css (DONE)
- [x] 4. pytest: vi slowest, wait ratio ~1.35 within band, resolve-rate gap, completeness, API 200
- [x] 5. ruff + full pytest green
- [x] 6. chromium probe: assert equity pane + screenshot (PROBE_MODE3 OK)
- [x] 7. commit + push
- [x] 8. board comment with report + screenshot
