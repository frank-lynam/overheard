# Overheard

An AI voicemail console that catches what busy humans miss.

Overheard replays one day of voicemail at a fictional federal call center, the
*Federal Benefits Service Center*, plus its three-year archive, through four modes:

| Mode | What you see |
| --- | --- |
| **0 · No AI** | Today's way: an agent listens to every message, oldest first, and types it up. |
| **1 · Obvious AI** | Every message read for you: a summary, the details, how urgent it is, who should handle it, a translation and a suggested reply. People check and correct it. |
| **2 · Non-obvious AI** | The day connected: an outage spotted from the first few callers, answers found in the case record, deadlines caught, repeat callers combined. |
| **3 · Impossible without AI** | Three years of calls read at once: why people call, what letters set the phones ringing, early warnings that were missed, questions no help article answers. |

A scoreboard plays out the day in each mode and shows what changes: when the
caller in real hardship is reached, how many deadline-bound requests are met,
how many callers are reached at all, and how much agent time comes back.
Hover over anything for what it means. `/present` is a talk-through deck of
Mode 3.

All data is synthetic, and the default mock mode runs fully offline.

```sh
pip install overheard
overheard serve          # then open http://127.0.0.1:8000
```

## A real model

Point it at any OpenAI-compatible endpoint:

```sh
export OVERHEARD_LLM_MODE=live          # mock | live | record | replay
export OVERHEARD_LLM_BASE_URL=https://...
export OVERHEARD_LLM_API_KEY=...
export OVERHEARD_LLM_MODEL=...
overheard serve
```

With the endpoint set, `OVERHEARD_LLM_MODE=record overheard record` runs the
model over the whole day once and saves its answers; `OVERHEARD_LLM_MODE=replay`
then serves those answers with no network at all, for a demo that can't be
surprised. `OVERHEARD_DB_PATH`, `OVERHEARD_HOST` and
`OVERHEARD_PORT` set where the data lives and where it listens.

See [docs/DESIGN.md](docs/DESIGN.md) for the design.
