# Goal

Mode 3 view 6 (letter lab) live end to end: paste a draft notice, get detected notice type, predicted call-volume range from similar past mailings, example questions from real archive readers, and a before/after rewrite — with tests recovering the planted Form 22-B excess.

## How it works

Read the real thing: docs/DESIGN.md:112 defines the feature; events.py plants the Form 22-B mailings (peak 9.0/day, 50 days, decay exp(-3*age/days)) and the generator uses the same decay math (generator.py:109), so predicted mailing impact is recoverable from contacts. Archive contacts carry root_cause + phrasing text (real reader questions). Existing pattern: analytics module (equity.py) → GET route (routes.py:423) → m3-pane in index.html + render fn in mode3.js + lazy load in main.js + probe asserts in tools/probe_mode3_ui.py.

## Why it doesn't

No analytics/letter_lab.py, no /api/letter-lab route, no letter-lab pane in index.html/mode3.js/main.js, no tests: the planted 22-B confusion pattern exists only in events.py and the UI has 5 of the 6 mode-3 panes.

## What would

src/overheard/analytics/letter_lab.py: (a) notice detection — score the draft against driver phrasings by word overlap, return top driver; (b) volume prediction — for mailing-type drivers, sum the generator's event decay model over the event's days using measured window contacts (like event-impact's window math), and scale by wording-clarity; (c) example questions — sample real contact texts for that driver; (d) rewrite — rewrite the draft with a rule-based clearer-letter transform (split long sentences, active voice, explicit "what to do by when" block) and predict the clear version's lower confusion share. POST /api/letter-lab in routes.py. Mode-3 letter-lab pane (textarea + test button + results with prov badge "plain code · archive patterns"). Tests: seeded 22-B letter detects form-22b-confusion, predicted volume within band of the actual 22-B mailing windows, rewrite reduces predicted questions, API 200 with both letter+rewrite. Ruff --no-fix near CHECKLIST.md; full pytest; extend probe (letterLab pane) + screenshot; commit/push; board comment + screenshot.

## Steps

- [x] 1. analytics/letter_lab.py (detection + volume prediction + questions + rewrite)
- [x] 2. POST /api/letter-lab route
- [x] 3. Mode-3 letter-lab pane: index.html + api.js + main.js + mode3.js renderLetterLab + css
- [x] 4. pytest: 22-B detection, volume band vs planted, rewrite improves, API 200
- [x] 5. ruff --no-fix + full pytest green
- [x] 6. extend chromium probe: letter-lab pane + screenshot
- [ ] 7. commit + push
- [ ] 8. board comment with report + screenshot
