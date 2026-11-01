# Goal

giddy-sparrow: phase-6 release & rehearsal — record/replay fixtures, presenter mode, offline dry-run, 0.1.0 release prep, pushed and handed back to review

## How it works

Read the ticket, CLAUDE.md, DESIGN.md phase 6, publish.yml, and the repo: llm/{cache,replay,provider,run}.py already implement the ResponseStore and ReplayProvider; analyze.py/resolution.py/incidents.py all call run_task with write=False so nothing ever lands in the store; cli.py has a `record` stub that exits 2; no presenter view exists in static/ (main.js only has mode stepper + workbench + tabbed mode-3); PyPI already has overheard 0.0.2; publish.yml does tag→PyPI, workflow_dispatch→TestPyPI.

## Why it doesn't

Missing: (1) `overheard record` never populates the store (stub, exit 2); (2) no presenter/talk-through view; (3) no proof that replay of a recorded store is identical and fully offline; (4) version is still 0.0.2 and no wheel-contents test.

## What would

Implement `overheard record` that runs every task on the seeded day through the real pipeline with write=True (mock by default, live host under OVERHEARD_LLM_MODE=record); add a test proving record→replay replay gives byte-identical task outputs with zero network; build a vanilla-JS /present full-screen deck (keyboard nav, reveal animations + speed, assumptions panel) over the Mode-3 analytics endpoints; add tools/probe_presenter.py + screenshots and an offline rehearsal dry-run script (seed→record→replay serve→drive endpoints with network cut); bump to 0.1.0, add a wheel-contents test, python -m build + twine check + clean-venv install+serve smoke; ruff --no-fix and full pytest throughout; commit, push branch ticket/giddy-sparrow + tag v0.1.0 (announced), hand back with Done comment + status review. Verify: 95+ tests green, probe prints OK, screenshots exist and look right, tag exists on deploy remote.

## Steps

- [x] 1. Implement overheard record (store population via real pipeline, write=True)
- [x] 2. Test: record then replay, identical outputs, zero network
- [x] 3. Presenter mode /present deck (vanilla JS, keyboard nav, reveal + speed, assumptions panel)
- [x] 4. Ruff --no-fix + full pytest
- [x] 5. Offline rehearsal dry-run: seed→record→replay serve→probe + screenshots
- [ ] 6. Release prep: version 0.1.0, wheel-contents test, README touch-ups
- [ ] 7. Release verify: build + twine check + clean-venv install + serve smoke
- [x] 8. Commit, push branch + tag v0.1.0 (announced), Done comment + status review
