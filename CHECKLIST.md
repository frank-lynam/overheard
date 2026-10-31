# Goal

Mode 1 "Obvious AI" UI works end-to-end offline: analysis bundle (all 7 tasks) per message with provenance + confidence + spans, mode-1 urgency queue with team routing and m37 re-sort animation, editable AI fields whose corrections feed the scoreboard accuracy.

## How it works

LLM layer landed (commit fae4dd0): 7 task modules with build() -> Task, run_task() -> LLMResult{data,provenance,model,key} with cache/retry/fallback. Steps 1-2 done and green (ruff clean, 40 passed). No analyze.py, no analysis/corrections tables, no mode-1 routes, no mode-1 UI yet.

## Why it doesn't

There is no pipeline that runs the tasks for a message, nothing persisted to query, and the frontend only has mode 0.

## What would

Backend: extend 3 task outputs + add routing task + mock updates (done); pipeline/analyze.py runs all tasks and persists to sqlite `analysis`; corrections table + endpoint; /queue?mode=1 and /accuracy. Frontend: mode-1 transcript with low-confidence words, panels for summary/extraction/confidence+spans/intent+urgency+rationale/routing/sentiment/translation, editable fields with provenance badges + why-popover logging corrections, urgency re-sort animation, scoreboard accuracy. Offline tests, ruff+pytest green, chromium smoke + screenshot, commit+push, board comment.

## Steps

- [x] 1. Extend task outputs (summary.short, extraction envelopes+program+requestedAction, intent rationale) + routing task + prompt/example updates
- [x] 2. Mock: confidence, spans found in script, program/action, rationale, routing team
- [x] 3. pipeline/analyze.py: run all 7 tasks, persist analysis rows, return bundle with provenance
- [x] 4. API: POST/GET analysis, corrections, /queue?mode=1, /accuracy; db tables in open_db
- [x] 5. Frontend message pane mode 1: transcript + AI panels + confidence/spans + provenance badges + why-popover + editable fields + corrections
- [x] 6. Frontend queue mode 1: urgency order, team badges, m37 re-sort animation; scoreboard mode 1: accuracy + corrections
- [x] 7. CSS for panels/badges/transcript highlights
- [x] 8. Tests (offline) for tasks/mock/analyze/queue/accuracy/corrections; ruff + full pytest green
- [ ] 9. Chromium smoke test + screenshot
- [ ] 10. Commit + push + board comment; tick Mode 1 item + PUT checklist; tidy up
