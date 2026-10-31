# Overheard — project brief for Claude Code

The full design and implementation plan lives in `docs/DESIGN.md` (exported from the design doc). Read it before starting. This file is the short version: the decisions you must not drift from, the build order, and how to work in this repo.

**Overheard** is the product name: an AI voicemail console that catches what busy humans miss. PyPI package, import package, and CLI are all `overheard`; environment variables use the `OVERHEARD_` prefix.

## What this is

A demo application that shows how AI streamlines call-center voicemail work for a fictional federal agency, the *Federal Benefits Service Center* (FBSC). The same synthetic data runs through four progressive modes:

| Mode | Name | Point |
| --- | --- | --- |
| 0 | No AI | Baseline: manual inbox, measured cost (~7 agent-hours for 60 voicemails) |
| 1 | Obvious AI | Per-message transcription, summary, extraction, urgency, routing, translation, draft reply |
| 2 | Non-obvious AI | Cross-message spike detection, resolution without callback (LLM tool use), deadline-bound request detection, repeat-caller linking |
| 3 | Impossible without AI | Archive-wide cost by root cause, event impact, caller journeys, promises vs. outcomes, letter pre-testing, equity, ask-the-archive |

## Fixed architecture decisions

- **Python package** `overheard`, import name `overheard`, src layout, built with **hatchling**. Python ≥ 3.11.
- **Backend:** FastAPI on **uvicorn**. Console script `overheard` with subcommands `serve`, `seed`, `record`, `batch-label`.
- **Front end:** vanilla JavaScript ES modules, plain CSS with custom properties, hand-written SVG charts. **No build step, no framework, no npm.** Ships as package data under `src/overheard/static/` and is served by the same uvicorn process.
- **Browser ↔ server:** REST plus server-sent events (`/api/events`). The browser never talks to an LLM or holds an API key.
- **LLM:** any **OpenAI-compatible** host, called with the `openai` Python SDK (`AsyncOpenAI(base_url=..., api_key=...)`). Providers implement one `Protocol`: `MockProvider`, `OpenAICompatProvider`, `ReplayProvider`. Mode is chosen by `OVERHEARD_LLM_MODE` = `mock | live | record | replay`. **Default is `mock`**, and the whole app must work fully offline in mock mode.
- **Mock outputs come from the ground truth.** `MockProvider` builds each task's output from the message's truth labels, with a seeded share of realistic mistakes (about 90–95% accurate), so mock mode needs no hand-written fixtures and the scoreboard's accuracy stays honest offline.
- **One response store.** Live LLM responses are kept as JSON files keyed by (task, input hash, model): `live` uses them as a cache, `record` writes them, `replay` only reads them and never touches the network. No separate SQLite LLM cache.
- **The day is computed up front.** The pipeline runs over the whole day per mode and stamps when each thing would happen (e.g. the incident alert at 9:40); the browser's replay control (1×, 10×, 60×) reveals it by time. SSE is only for live LLM progress.
- **Text only, for now.** No audio until nearer 1.0.0. `TranscriptionProvider` stays as a seam and returns the script. Mode 0's "play" reveals the transcript at speaking pace (~150 words a minute), so listening still costs what it would.
- **Structured output:** each LLM task is a module with system prompt, few-shot examples, a pydantic output model, and optional tools. Use `json_schema` response_format when the host supports it (found out lazily on the first live call and remembered; startup never waits on the network), else JSON mode + pydantic validation. On validation failure: retry once with the error appended, then fall back to the mock fixture and mark provenance `fallback`.
- **Rule of thumb:** LLM for language judgment; plain code for counting, statistics, joins, and baselines.
- **Storage:** SQLite (stdlib `sqlite3` or a thin wrapper) for seeded data and the pipeline cache keyed by (message, mode). LLM responses live in the response store (above).
- **Adapters** (all `Protocol` + mock + live): `TranscriptionProvider` (mock now; AWS Transcribe later), `LLMProvider`, `CaseBackend` (mock now; real system of record later). These are the seams for a future real integration; keep business logic out of them.
- **Data is synthetic and deterministic.** `overheard seed` generates the 60-message "today" queue (hand-written scripts in `data/seed_today.json` with ground-truth labels) and a ~15,000-contact, 3-year archive from a fixed seed. Same seed → byte-identical database. Every planted pattern has a test that the analytics recover it (e.g. Form 22-B tops the root-cause Pareto, within ±10% of its planted cost).
- **Mode 3 is measured, not only planted.** Before a demo, `overheard batch-label` labels a sample of the archive (~1,000 contacts) with the live LLM; Mode 3 shows that measured accuracy against the truth and scales from it.
- **Config:** pydantic-settings, `OVERHEARD_*` environment variables (`OVERHEARD_LLM_MODE`, `OVERHEARD_LLM_BASE_URL`, `OVERHEARD_LLM_API_KEY`, `OVERHEARD_LLM_MODEL`, `OVERHEARD_LLM_TIMEOUT`, `OVERHEARD_DB_PATH`, `OVERHEARD_SEED`, `OVERHEARD_HOST`, `OVERHEARD_PORT`).

## Repo layout

```text
pyproject.toml
src/overheard/
  cli.py  app.py  config.py
  api/          queue, analysis, replay, incidents, archive, letter_lab, ask, settings
  pipeline/     stages/, modes.py, runner.py
  llm/          provider.py, openai_compat.py, mock.py, replay.py, cache.py, tasks/
  adapters/     transcription/, backend/
  data/         models.py, db.py, generator.py, templates.py, events.py, seed_today.json
  analytics/    root_causes.py, event_impact.py, journeys.py, promises.py, equity.py
  static/       index.html, css/, js/core/, js/ui/, js/charts/
fixtures/
tests/
.github/workflows/  ci.yml, publish.yml
docs/DESIGN.md
```

## Build order (stop and demo after each phase)

1. **Foundation** — pyproject, CLI, FastAPI app factory serving static files, SQLite layer, pydantic models, seeded generator, the 60 scripts with truth labels, mock case backend, CI (ruff + pytest). Done when `pip install -e . && overheard seed && overheard serve` shows an empty shell with a mode stepper.
2. **Mode 0** — chronological inbox, player (text fallback if no audio), manual form, lookup panel, effort timer, "work the queue" simulation, scoreboard v1.
3. **Mode 1 + LLM layer** — provider Protocol and three providers, task modules, validation/retry/fallback, cache, record mode, capability probe; summary, extraction, intent/urgency, translation, sentiment, draft reply; priority sort, routing, provenance badges, edits scored against truth.
4. **Mode 2** — similarity grouping (TF-IDF or host embeddings), spike detection + incident card, tool-use lookups for resolution without callback, callback brief, deadline-bound detection with keyword backstop and deadline clocks, repeat-caller linking, missing-info recovery, callback windows. **MVP gate: Modes 0–2 run end to end.**
5. **Mode 3** — root-cause Pareto with cost model first, then event impact, journeys, promises, equity, letter lab, ask-the-archive, knowledge gaps.
6. **Release and rehearsal** — presenter mode, publish workflow (TestPyPI → PyPI via trusted publishing), record fixtures against the live host, offline dry run in replay mode.

## Packaging and release

- Plain 0.x versions on public PyPI (`0.1.0`, `0.2.0`...; `pip install overheard`, no `--pre`). Single source of version in `src/overheard/__init__.py`.
- Static files and `seed_today.json` must be included in the wheel; add a test that builds the wheel and checks they are present.
- `publish.yml` publishes on tag `v*` to TestPyPI, then PyPI, using trusted publishing (no stored tokens). Don't publish anything without asking first.
- Check the package name is available on PyPI before the first upload; ask if it isn't.

## Working agreements

- Mock mode must always work with no network. Never make tests depend on a live LLM.
- Tests: pytest for pipeline stages, pydantic schemas, API routes (httpx `AsyncClient`), generator determinism, and wheel contents.
- Lint with ruff; type hints throughout.
- AI never sends anything outbound without a human approval step in the UI.
- Every AI field carries provenance (`mock | llm | fallback | human`) and, where applicable, a source span.
- No real PII anywhere. Keep the agency fictional.
- Keep the front end dependency-free; if you think you need a library, ask first.

## Settled (Oct 31, 2026)

- LLM: an external OpenAI-compatible host; configured with an endpoint and API key (`OVERHEARD_LLM_BASE_URL`, `OVERHEARD_LLM_API_KEY`, `OVERHEARD_LLM_MODEL`).
- Releases: public PyPI, plain versions below 1.0.0.
- Text-only transcripts until nearer 1.0.0; audio integration then.

## Still open (ask rather than guess)

- Who the audience is (internal leadership or a government customer), and the demo date.
- Whether the fictional agency should mirror a real customer's domain.
