# Overheard

An AI voicemail console that catches what busy humans miss.

Overheard replays one day of voicemail at a fictional federal call center, the
*Federal Benefits Service Center*, plus its three-year archive, through four modes:

| Mode | What you see |
| --- | --- |
| **0 · No AI** | Today's way: an agent listens to every message, oldest first, and types it up. |
| **1 · Obvious AI** | Every message read for you: a summary, the details, how urgent it is, who should handle it, a translation and a suggested reply. Robocalls, scams and silence are kept out before anyone listens, and code words ("shut off", "senator") put a call in front of a person at once. People check and correct it. |
| **2 · Non-obvious AI** | The day connected: an outage spotted from the first few callers, answers found in the case record, deadlines caught, repeat callers combined, and the policies or notices that apply, quoted from the caller. Each real problem becomes a ticket for the team routing memory proposes, and a person's correction teaches the next proposal. |
| **3 · Impossible without AI** | Three years of calls read at once: why people call, what letters set the phones ringing, early warnings that were missed, questions no help article answers, and the callers who had today's problem weeks before anyone knew. |

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

A gateway that speaks the OpenAI format with your own key (the GovCloud
endpoint, for example) is this same setup: its URL (up to `/v1`), your key,
and the model name it expects. Overheard asks once whether it takes
`json_schema` structured output and otherwise uses JSON mode; record mode
always uses JSON mode.

Or Claude, on its own API or on Amazon Bedrock:

```sh
export OVERHEARD_LLM_MODE=live
export OVERHEARD_LLM_PROVIDER=anthropic   # openai_compat (default) | anthropic | bedrock
export OVERHEARD_LLM_MODEL=claude-opus-5-5  # the default; on Bedrock, anthropic.claude-opus-5-5
# anthropic: OVERHEARD_LLM_API_KEY, or the SDK's own ANTHROPIC_API_KEY / `ant auth login`
# bedrock:   pip install 'overheard[bedrock]'; OVERHEARD_AWS_REGION=us-gov-west-1 and the usual AWS credentials
overheard serve
```

`OVERHEARD_LLM_EFFORT` (default `medium`) sets Claude's effort, and
`OVERHEARD_LLM_TASK_MODELS` gives single tasks their own model, as JSON
(`{"junk_classify": "claude-haiku-5-5", "team_propose": "claude-opus-5-5"}`);
the model is recorded with every answer.

With the endpoint set, `OVERHEARD_LLM_MODE=record overheard record` runs the
model over the whole day once and saves its answers; `OVERHEARD_LLM_MODE=replay`
then serves those answers with no network at all, for a demo that can't be
surprised. `OVERHEARD_DB_PATH`, `OVERHEARD_HOST` and
`OVERHEARD_PORT` set where the data lives and where it listens.

## Tickets in hearthboard

By default tickets go to a board inside Overheard. To file them in a real
[hearthboard](https://github.com/frank-lynam/hearthboard) (0.2.0 or later), one
project per team, run `python tools/demo_board.py` from a checkout: it sets the
board up and prints the two settings to export, `OVERHEARD_WORKFLOW_URL` and
`OVERHEARD_WORKFLOW_TOKEN`. Tickets then arrive as proposals in the proposed
team's project; accepting, moving or declining them there is read back within
seconds, and a move changes the next similar proposal.

## Working on it

`pip install -e '.[dev]'`, then `pytest` (offline, no model) and `ruff check`.
`python tools/rehearse_offline.py` records the demo's whole walk and replays it
with the network cut, failing on any answer that isn't in the store.
[CLAUDE.md](CLAUDE.md) has the code map and the decisions not to drift from;
[docs/DESIGN.md](docs/DESIGN.md) has the design and the demo script.
