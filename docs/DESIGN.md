# Overheard — Design & Implementation Plan

Oct 31, 2026 · @Frank

> **Revised after review (Oct 31, 2026).** Where this document and the project `CLAUDE.md` disagree, `CLAUDE.md` wins. The changes: mock outputs are derived from the ground truth (no hand-written fixtures); one JSON response store serves live caching, record and replay; the day is computed up front and replayed in the browser (SSE only for live LLM progress); text only for now, with Mode 0 revealing transcripts at speaking pace; Mode 3 adds a measured sample labelled by the live LLM; each planted archive pattern has a recovery test; the capability probe is lazy; releases are plain 0.x versions on public PyPI.

## Overview

We will build Overheard, an AI voicemail console: a vanilla JavaScript front end served by a Python backend (FastAPI on uvicorn) that wraps an OpenAI-compatible LLM hosted elsewhere, released on PyPI as a pre-release package. It replays one day of voicemail at a fictional federal call center, plus a three-year archive. The presenter steps the same data through four modes: **No AI**, **Obvious AI**, **Non-obvious AI**, and **Impossible without AI**. A running scoreboard shows what each mode adds.

**Goals**

- Show a measurable before-and-after on the same workload: agent hours, callbacks avoided, deadline-bound requests caught, and dollars saved.
- Take the conversation past "AI transcribes and summarizes" to avoided callbacks, patterns across messages, and analysis of the whole archive.
- Install and run anywhere: pip install --pre overheard, then overheard serve. The front end still needs no build step, and mock mode works fully offline with no LLM.
- Swap each mock for a real model behind a stable server-side interface: point the backend at any OpenAI-compatible endpoint, with no UI changes. The same interfaces are the seams for a later real integration.

**Non-goals:** production readiness, real recordings or PII, telephony integration, or multi-user features.

## The four modes

The whole story is in the four modes: the same 60 voicemails go from a 7-hour slog, to a sorted inbox, to a queue that mostly clears itself, and then to a view of the entire operation. Modes add to each other. Each one keeps everything from the one before, and the scoreboard carries across mode switches so the audience watches the numbers move.

| Mode | The question it answers | Headline capabilities | The moment to show |
| --- | --- | --- | --- |
| 0 · No AI | What does this cost today? | Chronological inbox, audio playback, manual entry and lookup, timing measured as you work | A "work the queue" fast-forward shows the urgent message at position 37 not reached until 2:40 pm |
| 1 · Obvious AI | Can we read faster? | Transcription, summary, field extraction, intent and urgency, priority sort, routing, translation, draft replies | Message 37 jumps to the top; a Vietnamese voicemail arrives already translated and routed |
| 2 · Non-obvious AI | Can we need fewer calls and miss nothing? | Spike detection across messages, resolution without a callback, deadline-bound request detection, repeat-caller linking, auto-request for missing info, pre-researched callback briefs | A portal-outage incident is flagged at 9:40 from 30 scattered messages; 40% of the queue closes with no phone call |
| 3 · Impossible without AI | What is the whole system telling us? | Cost by root cause, impact of each event, caller journeys, promises vs. outcomes, letter pre-testing, equity analysis, knowledge gaps, ask-the-archive | "This one notice cost an estimated $600K a year in calls" |

## Synthetic dataset

The demo depends on a scripted "today" queue with planted signals, plus a procedurally generated archive. Both are fully synthetic, and both carry hidden ground-truth labels so every AI output can be scored. The fictional agency is the *Federal Benefits Service Center* (FBSC), which handles benefit payments, address changes, portal accounts, and document submissions.

**Today's queue (60 hand-written voicemails)**

- 1 buried urgent message at position 37: a caller facing a utility shutoff because of a delayed payment.
- 28 messages about the same portal login error, starting at 9:12 am and phrased many different ways. None say "outage."
- 4 non-English messages: Spanish, Vietnamese, Tagalog, and one that mixes English and Spanish.
- 1 caller who leaves 3 messages over two days, getting more frustrated each time.
- Deadline-bound requests: 2 that mention contacting a member of Congress, 1 records request worded informally (it never says "FOIA"), 1 legal threat, and 1 welfare concern.
- 12 status questions ("did you get my form," "when is my payment") that the mock backend can answer.
- 6 messages missing a case number, where caller ID still matches a known case.
- Realistic mess: rambling, self-corrections, numbers read aloud ("five five five, uh, oh one two"), and callback-time cues ("I'm at work until five").

**Archive (about 15,000 contacts over 3 years)**

- Generated in Python from a fixed seed by overheard seed, so no large data files are committed and every run produces identical data.
- Built from about 40 call-driver templates with randomized wording, caller, region, language, and timing.
- Volume is driven by an events calendar, so effects are recoverable: notice mailings, portal releases, policy changes, and payment-date shifts. One notice ("Form 22-B re-verification letter") is deliberately confusing and drives a large, steady excess in calls.
- Planted patterns: callers stuck in loops, broken callback promises concentrated in one issue type, a slower resolution time for one language, and a weak signal that grew into a spike months later.

**Mock backend records**

- Cases: status, payment schedule, documents received, last action, and assigned team.
- Caller directory mapping phone number to case.
- Events calendar, knowledge-base articles (with deliberate gaps), and callback notes containing promises.

**Audio:** optional. Generate it with Amazon Polly using varied voices, or have coworkers record the 60 scripts. Mock transcription returns the script text with simulated latency and a few low-confidence words.

## Mode 0 · No AI

Mode 0 establishes the baseline cost honestly and keeps it on screen: clearing 60 voicemails by hand is roughly 7 agent-hours, and the urgent message waits until mid-afternoon.

- **Chronological inbox.** Shows only time, caller ID, and duration. No content is visible until you play the message.
- **Audio player** with scrubbing. The transcript stays hidden.
- **Manual entry form:** caller name, callback number, case number, category, priority, notes, and disposition.
- **Manual lookup panel** against the mock backend (search by name, phone, or case number). This shows the swivel-chair work of jumping between systems.
- **Measured effort:** real time spent on each message, plus a configurable handling time (3.5 minutes by default) that extrapolates the workload clock.
- **"Work the queue" simulation:** a fast-forward of a single agent working in order. It stamps when each message is first touched, including the urgent one at 2:40 pm and the first portal-error message whose pattern nobody connects.

The presenter plays two or three real messages live so the audience feels the pain, then runs the simulation for the rest.

## Mode 1 · Obvious AI

Mode 1 is the version every vendor shows: each message is processed on its own. That turns listening into reading and sorts the queue by need. It cuts handling time sharply but does not reduce how much work exists.

1. **Transcription** (mock). Low-confidence words are highlighted, and clicking a word jumps the audio to that point.
2. **One-line summary** plus a short summary.
3. **Structured extraction:** caller name, callback number (normalized from spoken digits), case number, program, and requested action. Each field shows a confidence score and the span of the transcript it came from.
4. **Intent and urgency.** An intent category, plus a 1–5 urgency score with a one-sentence rationale.
5. **Priority queue and routing.** The queue re-sorts by urgency and assigns each message to a team queue. A short animation moves message 37 to the top.
6. **Language detection and translation** to English, keeping the original text alongside.
7. **Sentiment and frustration** level.
8. **Draft callback script** or written reply, which the agent edits before use.

Every AI field is editable, and edits are logged as corrections. That record later feeds the accuracy numbers on the scoreboard and supports the message that people stay in control.

## Mode 2 · Non-obvious AI

Mode 2 shifts the goal from handling calls faster to needing fewer of them and missing nothing. It works by reasoning across messages and taking action against backend systems.

1. **Live spike detection.** Messages are grouped by similarity as they arrive. When a group grows faster than its baseline, the LLM names it and drafts an incident card: first seen, count, probable cause, and suggested actions (an IVR banner, a ticket for the portal team, a holding reply sent to everyone affected).
2. **Resolution without a callback.** The LLM chooses backend lookups through tool calls (case status, payment schedule, documents received). If the question is answerable, it drafts a text or email reply that an agent approves with one click. The scoreboard tracks the share of messages closed with no call.
3. **Pre-researched callback brief.** For messages that do need a call: the case history, prior contacts, what was promised, and the likely answer. The agent dials already knowing the answer.
4. **Deadline-bound request detection.** Flags mentions of a member of Congress, records requests, legal threats, welfare or safety concerns, and discrimination complaints, even when not stated plainly. Each flag starts a workflow with a deadline clock (deadlines configurable per agency policy, for example FOIA's 20-business-day window). Keyword rules back up the LLM so recall stays high.
5. **Repeat-caller linking.** Matches on caller ID, name, and case number, with the LLM settling ambiguous cases. Three messages collapse into one item with an escalation note, such as "3rd contact in 48 hours, rising frustration."
6. **Missing-info recovery.** Infers the case from caller ID. If it can't, it sends the caller an automatic request for the missing detail before any agent touches the message.
7. **Callback window extraction.** "I'm at work until five" becomes a scheduled callback slot, which cuts down phone tag.
8. **Belief vs. record mismatch.** Detects when the caller's understanding contradicts the record (for example, they think a payment was missed when it is actually scheduled) and drafts a reassurance reply.
9. **Next best action.** Suggests a knowledge-base article and a disposition for each item.
10. **Rest-of-day forecast.** Projects incoming volume from the morning's spikes so a supervisor can reassign staff.

## Mode 3 · Impossible without AI

Mode 3 moves from the queue to the archive. A QA team samples a few percent of calls; the AI reads all 15,000 and connects them to events and outcomes. Each view below would take a person months of listening.

1. **Cost by root cause.** Every archived contact gets a root-cause label. Multiplying by handling time and a configurable fully loaded labor rate gives a Pareto chart of annual cost by cause. This is the headline: "The Form 22-B letter cost an estimated $600K a year."
2. **Impact of each event.** Call themes are overlaid on the events calendar. For each mailing, release, or policy change, the view shows excess calls above baseline, how long the effect lasted, and what confused people. For example: "Portal release 4.2 caused about 6,100 extra calls over 9 days."
3. **Caller journeys.** Every contact from the same caller is linked across years. The view lists callers stuck in loops (3 or more contacts about one issue with no resolution) and the process steps where those loops start.
4. **Promises vs. outcomes.** Commitments are extracted from callback notes ("you'll have it in 10 days") and checked against what the backend shows happened. Results show the broken-promise rate by issue type and team.
5. **Letter pre-testing.** Paste in a draft notice. Simulated readers built from real confusion patterns in the archive raise their questions. The tool predicts the top questions and a call-volume range (based on similar past mailings) and suggests rewrites, with a before-and-after comparison.
6. **Equity of service.** Resolution time and repeat-contact rate by language and region, with disparities flagged and example messages attached.
7. **Knowledge-gap mining.** Finds questions callers ask often that no knowledge-base article answers, and drafts FAQ and IVR text to fill the gap.
8. **Missed weak signals.** Finds issues that started small months before they spiked, and estimates how much earlier they could have been caught.
9. **Ask the archive.** Plain-English questions ("Why did calls from Ohio double last March?") are answered over pre-computed totals, with example messages cited as evidence.
10. **Event-driven staffing forecast.** Uses upcoming mailings and releases to project call volume and the agent hours needed.

The demo cannot run 15,000 LLM calls live. Archive labels are therefore produced ahead of time: by the mock layer, or by the overheard batch-label command against the live LLM. At runtime the LLM handles naming, explanation, letter tests, and questions, working on totals plus a sample of messages.

## Architecture

&#91;embedded content: architecture · 4 layers, 14 modules\]

The browser never calls the LLM or data adapters directly. Everything goes through the Python service, which keeps API keys server-side and gives a later real integration clean seams to replace.

- **Packaging.** One Python package, overheard, built with hatchling in a src/ layout. The vanilla JS front end ships inside it as package data. The console command `overheard serve` starts uvicorn with the API and static files on one port.
- **Front end.** Still no build step: ES modules, a small publish/subscribe store, and the mode stepper. It calls REST endpoints and listens to server-sent events for the replay clock, incidents, and pipeline progress.
- **API.** FastAPI routes: `/api/queue`, `/api/messages/{id}/analysis?mode=`, `/api/replay`, `/api/incidents`, `/api/archive/*`, `/api/letter-lab`, `/api/ask`, `/api/settings`, `/api/events` (SSE).
- **Pipeline.** Server-side stages (transcribe → understand → enrich → link → detect → act). Each stage is an async function `(message, ctx) → patch`, registered with a minimum mode. Results are cached per message and mode in SQLite, so switching modes is instant.
- **Data.** `overheard seed` runs a seeded generator that writes the today queue and the 3-year archive into SQLite. Pydantic models are shared by the API and the pipeline.
- **Adapters.** Python `Protocol` classes for `TranscriptionProvider`, `LLMProvider`, and `CaseBackend`, each with a mock and a live implementation chosen by config.

```text
overheard/
  pyproject.toml            hatchling, src layout, overheard entry point, version 0.1.0a1
  src/overheard/
    cli.py                  serve, seed, record, batch-label
    app.py                  FastAPI app factory, static mount, SSE
    config.py               pydantic-settings (OVERHEARD_* environment variables)
    api/                    queue, analysis, replay, incidents, archive, letter_lab, ask, settings
    pipeline/               stages/, modes.py, runner.py
    llm/                    provider.py, openai_compat.py, mock.py, replay.py, cache.py, tasks/
    adapters/               transcription/, backend/
    data/                   models.py, db.py, generator.py, templates.py, events.py, seed_today.json
    analytics/              root_causes.py, event_impact.py, journeys.py, promises.py, equity.py
    static/                 index.html, css/, js/ (core/, ui/, charts/)
  fixtures/                 recorded LLM responses for replay
  tests/                    pytest: pipeline, schemas, API, generator determinism
  .github/workflows/        ci.yml, release.yml
```

**Release path**

- PEP 440 pre-releases: 0.1.0a1, a2, and so on, then 0.1.0b1. Users install with `pip install --pre overheard`.
- Publish to TestPyPI first, then PyPI, from a GitHub Actions release workflow using trusted publishing, so no API tokens are stored.
- Confirm the package name is free on PyPI before the first upload.

**Path to a real integration**

- A live transcription adapter (AWS Transcribe or Whisper) and a voicemail ingest adapter (an S3 bucket or a telephony webhook).
- A `CaseBackend` adapter for the real system of record, read-only at first.
- Authentication through a reverse proxy (OIDC or CAC), audit logging of every AI suggestion and human decision, and Postgres in place of SQLite.

## Mock layer and LLM layer

The rule: use the LLM for judgments about language, and use plain code for counting, math, joins, and audio. Every service sits behind one interface with a mock implementation and a real one, chosen per task in Settings, so the demo can never be broken by a network failure.

| Task | Implementation | Why |
| --- | --- | --- |
| Transcription | Mock (later AWS Transcribe or Whisper) | Requires a speech model, not an LLM |
| Language detection and translation | LLM | Works well from transcript text |
| Summary, extraction, intent, urgency, sentiment | LLM, structured JSON output | Core language-understanding work |
| Draft replies and callback briefs | LLM | Generation grounded in backend data |
| Backend lookups for resolving without a callback | LLM tool use against the mock backend | The LLM decides which lookups answer the question |
| Deadline-bound request detection | LLM, plus keyword rules as a backstop | High recall matters more than precision |
| Message similarity and grouping | TF-IDF in Python, or the host's embeddings endpoint | Cheap and deterministic |
| Spike statistics and baselines | Code | Arithmetic, not judgment |
| Naming clusters and incidents | LLM | Describing a group of messages in words |
| Caller linking | Fuzzy match in code; LLM breaks ties | Most cases are mechanical |
| Archive labeling | Pre-labeled in the generator; optional offline LLM batch | Too many messages for live calls |
| Cost, event impact, equity statistics | Code over labels | Must be exact and reproducible |
| Letter pre-testing, ask-the-archive, narrative summaries | LLM | Synthesis and reasoning |
| Audio for the dataset | Offline, Amazon Polly | Build-time only |

**Provider interface.** Every LLM task runs on the server as `llm.run(task, input)`. A task module supplies the system prompt, a few examples, a pydantic output model, and optional tools. The live provider uses the `openai` Python SDK with a configurable `base_url`, so it works with any OpenAI-compatible host: vLLM, Azure OpenAI, a LiteLLM or Bedrock gateway, or Ollama.

```python
# src/overheard/llm/provider.py
class LLMProvider(Protocol):
    async def complete(self, *, system: str, messages: list[dict],
                       output: type[BaseModel] | None = None,
                       tools: list[dict] | None = None,
                       temperature: float = 0.2) -> LLMResult: ...

# MockProvider          fixtures keyed by task + input hash, simulated latency, failure injection
# OpenAICompatProvider  AsyncOpenAI(base_url=OVERHEARD_LLM_BASE_URL, api_key=OVERHEARD_LLM_API_KEY),
#                       model=OVERHEARD_LLM_MODEL; json_schema response_format when the host
#                       supports it, else JSON mode + validation
# ReplayProvider        serves recorded responses only; never touches the network
```

Configuration comes from environment variables: `OVERHEARD_LLM_MODE` (mock, live, record, or replay), `OVERHEARD_LLM_BASE_URL`, `OVERHEARD_LLM_API_KEY`, `OVERHEARD_LLM_MODEL`, and `OVERHEARD_LLM_TIMEOUT`, plus an optional per-task override map.

**Reliability features**

- **Pydantic validation** on every response. On failure it retries once with the validation error appended, then falls back to the mock fixture and marks the field "fallback."
- **Response cache** in SQLite, keyed by task, input hash, and model.
- **Record and replay.** Record mode saves every live response as a fixture. Replay mode serves only fixtures, so demo day needs no network.
- **Capability probe** at startup checks whether the host supports structured output and tool calls, and falls back gracefully when it doesn't.

## Data model

The data model keeps the raw input, the AI's output, and the ground truth in separate objects. That way any mode can be re-run from cache, and any AI field can be scored against truth.

```js
/** @typedef {{ id, receivedAt, callerId, durationSec, audioUrl?, script, lang, truth: Truth }} Voicemail */
/** @typedef {{ intent, urgency, rootCause, obligations: string[], resolvableBy?: string, linkedTo?: string[] }} Truth */
/** @typedef {{ messageId, mode, transcript, summary, fields: Record<string, Field>, intent, urgency,
 *   rationale, sentiment, translation?, route, draft, brief?, resolution?, obligations: Obligation[],
 *   callbackWindow?, provenance: Record<string, 'mock'|'llm'|'fallback'|'human'> }} Analysis */
/** @typedef {{ value, confidence, sourceSpan: [number, number], editedBy?: 'human' }} Field */
/** @typedef {{ kind: 'congressional'|'records'|'legal'|'welfare'|'discrimination', evidence, dueAt, status }} Obligation */
/** @typedef {{ id, label, messageIds: string[], firstSeen, rate, baseline, probableCause, actions: string[] }} Incident */
/** @typedef {{ id, callerId, name, region, lang, status, payments: Payment[], docs: Doc[], lastAction, team }} Case */
/** @typedef {{ id, date, type: 'mailing'|'release'|'policy'|'payment-shift', name, description }} Event */
/** @typedef {{ id, caseId, at, channel, rootCause, lang, region, handleMin, resolved, promise?: Promise }} Contact */
/** @typedef {{ text, dueAt, kept: boolean|null }} Promise */
/** @typedef {{ mode, agentMinutes, callbacksAvoided, obligationsCaught, obligationsMissed,
 *   urgentFirstTouch, incidentLeadMin, accuracy: Record<string, {precision, recall}> }} Scoreboard */
```

On the server these are pydantic models in `data/models.py`, shared by the API and the pipeline; the front end receives the same shapes as JSON.

## UI design

The UI has one workbench for Modes 0–2 and one analytics dashboard for Mode 3, under a persistent top bar. The mode stepper is the main control: each step reveals new panels in place rather than switching to a different app.

**Top bar (always visible)**

- A mode stepper (0 → 3) with keyboard shortcuts 1 through 4.
- A scoreboard: agent hours to clear the queue, when the urgent message is first touched, callbacks avoided, deadline-bound requests caught or missed, incident lead time, and estimated dollars.
- Buttons for the assumptions panel and Settings.

**Workbench (Modes 0–2), three panes**

- **Queue (left).** Chronological in Mode 0, sorted by priority from Mode 1. Groups and collapsed repeat callers appear in Mode 2.
- **Message (center).** Audio player, then the transcript (Mode 1 and up), extracted fields with confidence and source highlighting, and the draft reply.
- **Context (right).** Case record, linked contacts, and in Mode 2: the callback brief, resolution-without-callback panel, and deadline clocks.
- **Incident banner** (Mode 2), which slides in when a spike is detected, linked to its cluster view.

**Analytics (Mode 3) tabs:** Root causes (Pareto chart) · Events (timeline overlay) · Journeys (loop list and flow) · Promises · Equity · Letter lab · Ask the archive.

**AI provenance everywhere.** Every AI-produced value carries a small badge (AI, human-confirmed, or fallback), a "why" popover showing its source span or rationale, and inline editing. AI suggestions and human-confirmed values look different.

**Presenter mode**

- A "replay the day" control with 1×, 10×, and 60× speed.
- Reveal animations for the key moments.
- A hidden notes drawer with the demo script.
- Large-type layout for projectors.

**Tech:** plain CSS with custom properties for themes. Charts are drawn with small hand-written SVG helpers (bar, line, Pareto, timeline, simple flow), with no framework and no chart library.

## Metrics

Every number on the scoreboard is computed from the simulation and ground truth, and every assumption behind it is visible and adjustable live. That is what makes the before-and-after credible to a skeptical audience.

| Metric | How it is computed | Changes in |
| --- | --- | --- |
| Agent hours to clear the queue | Sum of listen or read time plus handling time; avoided callbacks count as zero | Modes 1, 2 |
| Urgent message first touched | Time the simulated agent reaches it, given queue order | Mode 1 |
| Callbacks avoided | Messages closed by approved written replies ÷ total | Mode 2 |
| Deadline-bound requests caught / missed | Detected vs. ground truth; a miss is an item reached after its deadline | Modes 0 vs. 2 |
| Incident lead time | Minutes from the first related message to the alert, vs. the human baseline (noticed after N similar messages reach one agent) | Mode 2 |
| AI accuracy | Precision and recall per field against truth, including human corrections | Modes 1–3 |
| Estimated annual dollars | Agent hours × fully loaded rate × annualization; cost by root cause from the archive | Mode 3 |

The defaults live in the assumptions panel: 3.5 minutes handling per message, 6 minutes per callback, a $75/hour fully loaded rate, and 250 working days. Show accuracy honestly, including the misses; a demo that admits 92% beats one that claims 100%.

## Security, privacy, and compliance

The demo itself carries no real risk: all data is synthetic and mock mode makes no network calls. It should still show that we know what a real deployment would require, because a federal audience will ask.

**In the demo**

- Synthetic data only: no real recordings, names, or case numbers.
- Mock mode is the default. The LLM API key lives only in the server's environment; the browser never sees it.
- AI never sends anything outbound without a person approving it, and that rule is shown on screen.
- Every AI claim links to the transcript span or record it came from.

**Questions a real deployment must answer** (a slide's worth, not code)

- Privacy Act coverage of voicemail content and the relevant system of records notice; records-retention schedule for recordings and transcripts.
- Where model inference runs: a FedRAMP-authorized service (for example, Bedrock in GovCloud) inside the agency's authorization boundary; prompt and output logging.
- Bias evaluation before using the equity view or urgency scores operationally.
- Section 508 accessibility of the agent UI.
- Policy on how quickly deadline-bound requests must be handled, owned by the agency, not set by the model.

## Implementation plan

&#91;embedded content: estimates in focused dev-days, one developer · typed in chat\]

The full build is about 19 focused dev-days. Phases 0–3 (about 11.5 days) already make a strong demo, and Mode 3's root-cause view alone adds about 1.5 days if time is short.

**Phase 0 · Foundation**

- [ ] Package skeleton: pyproject (hatchling, src layout), `overheard` CLI, FastAPI app factory, static mount, CI with lint and tests
- [ ] Front-end shell, top bar, mode stepper, store, SSE client
- [ ] Pydantic models, SQLite layer, seeded generator for the queue and archive (`overheard seed`)
- [ ] Write the 60 voicemail scripts with ground-truth labels; mock case backend and caller directory

**Phase 1 · Mode 0**

- [ ] Chronological inbox, audio player, manual entry form, lookup panel
- [ ] Effort timer and "work the queue" simulation; scoreboard v1

**Phase 2 · Mode 1 and the LLM layer**

- [ ] LLM layer: provider Protocol with Mock, OpenAI-compatible, and Replay providers; pydantic validation; SQLite cache; record mode; capability probe
- [ ] Tasks: summary, extraction, intent and urgency, translation, sentiment, draft reply
- [ ] Priority queue, routing, provenance badges, inline edits feeding accuracy scoring

**Phase 3 · Mode 2**

- [ ] Similarity grouping, spike detection, incident banner and card
- [ ] Tool-use lookups, resolution-without-callback panel, callback brief
- [ ] Deadline-bound request detection with rule backstop and deadline clocks
- [ ] Repeat-caller linking, missing-info recovery, callback windows, belief-vs-record check

**Phase 4 · Mode 3**

- [ ] Root-cause Pareto chart with cost model (first, the headline)
- [ ] Event-impact timeline, caller journeys, promises vs. outcomes, equity view
- [ ] Letter lab and ask-the-archive (LLM over pre-computed totals); knowledge-gap list

**Phase 5 · Release and rehearsal**

- [ ] Presenter mode, replay speeds, reveal animations, assumptions panel
- [ ] Release workflow: build sdist and wheel, publish 0.1.0a1 to TestPyPI, verify `pip install --pre` in a clean virtualenv, then publish to PyPI with trusted publishing
- [ ] Rehearse against the live LLM host in record mode; freeze fixtures; offline dry run in replay mode

## Risks, open questions, and demo script

**Risks**

- *Live LLM output varies or fails on stage.* Rehearse with live calls in record mode, then present from replayed fixtures; fallback to mock per field.
- *Synthetic data looks too clean.* Write the 60 scripts by hand with real disfluencies, and have a colleague who has worked a call center review them.
- *Mode 3 numbers seem made up.* Show the assumptions panel and the ground-truth tables; frame dollars as an illustration of the method, not a claim about any real agency.
- *Scope creep.* Phases 1–3 alone make a strong demo; Mode 3 can ship with only the root-cause view.

**Open questions**

- [ ] Who is the audience: internal leadership, or a government customer?
- [ ] Demo date and available build time.
- [ ] Which LLM access is approved for this demo: which OpenAI-compatible host, and what authentication does it use?
- [ ] Is the PyPI package public, or should pre-releases go to a private index first?
- [ ] Recorded audio or text-only transcripts?
- [ ] Should the fictional agency mirror a real customer's domain?

**Demo script (about 15 minutes)**

Numbers are what the seeded day shows in mock and replay mode; a live recording can move them a little. Present
from replay (`tools/rehearse_offline.py` checks the whole walk offline first). Outcomes, not dollars: the console
shows what each mode gets done, and from Mode 1 on what it was without AI.

1. **Mode 0, by hand.** 180 voicemails, robocalls and silence included: until you've listened you can't tell.
   Play two, fill in one form, then "Work the queue": about 12.5 agent-hours, the urgent caller (the woman whose
   power is being cut off) reached at 4:18 pm, 36 of 59 real callers reached, 3 of 6 deadlines met, and nobody
   notices the portal is down.
2. **Mode 1, the obvious AI.** The junk filter keeps out all 121 junk calls and no real one (unsure calls still
   reach a person; any can be put back). A code word ("shut off") puts the hardship call in front of a person at
   once. Everything is transcribed, summarised, sorted and routed; show the Vietnamese message translated.
3. Pause: "This is what everyone shows. Here's what they don't."
4. **Mode 2, the non-obvious AI.** Replay the morning: the outage is spotted 17 minutes after its first caller,
   and one holding reply covers all of them. Nine messages need no callback: the case record already answers them,
   and a person approves each reply. Open the hardship message: "Applies here" shows which policies and notices
   fit, quoting the caller (hover a chip); an unsure one is amber, for a person to decide.
5. **Tickets that learn.** Open the tickets: each real problem becomes one ticket for the team routing memory
   proposes (93% right on past routings it hadn't seen). The first, a Form 22-B letter, is proposed to Outreach:
   move it to Benefits Processing. Reveal on: the next 22-B ticket is proposed to Benefits Processing, citing the
   one just moved. With `OVERHEARD_WORKFLOW_URL` set these are real hearthboard tickets (`tools/demo_board.py`).
   Close on the scoreboard: urgent caller reached at 10:13 am (6 hours sooner), 6 of 6 deadlines, all 59 callers,
   about 8.6 agent-hours back.
6. **Mode 3, impossible without AI.** Root causes: one letter takes about 1 in 8 of the centre's hours.
7. **Overlooked before today.** Today's outage, searched for in the past four weeks: 36 callers said "error 4012"
   from Feb 10 on, were taken for password resets and never ticketed. It could have been spotted 28 days sooner.
8. Letter lab: paste the rewritten notice; predicted calls drop. Then ask the archive a question from the audience.
9. Close: the same 180 voicemails, four very different days.
