# Goal

Build the LLM layer for overheard per CLAUDE.md: provider Protocol + Mock/OpenAICompat/Replay providers, JSON response store, structured-output validation/retry/fallback, capability probe, task modules (summary, extraction, intent/urgency, translation, sentiment, draft reply) — mock mode fully offline, provenance on every AI field, tests green.

## How it works

Repo at ~/work/tickets/fancy-wombat/repo has Foundation + Mode 0 done: FastAPI app, sqlite data layer (models, generator with truth labels), pipeline/simulate.py, api/routes.py, config.py with OVERHEARD_* env. No src/overheard/llm/ exists yet. CLAUDE.md specifies: provider Protocol (MockProvider, OpenAICompatProvider, ReplayProvider), OVERHEARD_LLM_MODE=mock|live|record|replay (default mock, offline), mock outputs from ground truth with 90-95% seeded accuracy, one JSON response store keyed (task, input hash, model), json_schema response_format with lazy capability probe, retry-once-then-fallback with provenance 'fallback', each LLM task = module with system prompt, few-shot, pydantic output model, optional tools.

## Why it doesn't

-

## What would

Create src/overheard/llm/ (provider.py Protocol + factory, mock.py, openai_compat.py, replay.py, cache.py response store, tasks/ modules) and wire OVERHEARD_LLM_MODE into config; tests for store, validation/retry/fallback, and mock-from-truth accuracy band. Then Mode 1 UI uses tasks next phase.

## Steps

- [x] 1. Read data/models.py, config.py, pipeline/simulate.py, api/routes.py to see truth labels, schema, seams
- [x] 2. Design llm module layout; write provider Protocol + config wiring
- [x] 3. Implement cache.py (JSON response store keyed task/input-hash/model)
- [x] 4. Implement mock.py (from truth, seeded 90-95% accuracy)
- [x] 5. Implement openai_compat.py (capability probe, json_schema, retry, fallback) + replay.py
- [x] 6. Implement tasks/ pydantic modules (summary, extraction, intent/urgency, translation, sentiment, draft reply)
- [x] 7. Tests: store roundtrip, validation/retry/fallback, mock offline determinism, accuracy band
- [x] 8. Run ruff + full pytest green
- [ ] 9. Commit + push, board update
- [ ] 10. Tidy up
