# Goal

Rework the Mode-3 dashboard: tab navigation across the 10 panes, lazy pane loading, and a single harmonized bar-row visual language.

## How it works

Mode 3 stacks 10 m3-pane sections in one scroll (index.html 23-34); main.js loads all 10 eagerly on mode entry; app.css has duplicated .m3-promise-* / .m3-equity-* bar-row blocks with mismatched fills (#c9573f vs #5773c9); docs/DESIGN.md specifies "Analytics (Mode 3) tabs".

## Why it doesn't

No tab nav exists in the HTML, main.js has no per-pane gating, and the bar rows are per-pane ad-hoc CSS instead of one shared component.

## What would

Add a .m3-tabs tablist to index.html with panes as role=tabpanel (inactive hidden); gate loading in main.js via a pane registry that fetches/renders only the active tab; collapse the promise/equity bar CSS into one shared style with a single accent fill. Update tools/probe_mode3_ui.py to click through tabs, assert nav + hidden panes, and point the server at its own repo. Verify: ruff --no-fix, full pytest, probe PROBE_MODE3 OK, screenshots of multiple panes. Then commit, push to deploy (announced), upload checklist (PUT), comment "Done", PATCH status review.

## Steps

- [x] 1. Add .m3-tabs tab bar + tabpanel roles/hidden to panes in index.html
- [x] 2. CSS: tab bar styling, hidden panes, unify promise/equity bar rows on one shared fill
- [x] 3. main.js: pane registry, lazy-load only the active tab, default to root-causes
- [x] 4. Update probe: tab bar in probe HTML, click through tabs, assert nav + hidden inactive panes, server from own repo
- [x] 5. Verify: ruff --no-fix, full pytest, run probe, inspect JSON + screenshots of several panes
- [x] 6. Commit + push to deploy ticket/mammoth-goblet (announced)
- [x] 7. Upload checklist (PUT) + 'Done' comment + PATCH status review
- [ ] 8. Tidy: update MEMORY.md, clean scratch files
