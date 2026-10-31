"""Post a progress comment to the fancy-wombat ticket."""
import json
import os
import urllib.request

body = (
    "Mode 1 backend is done and smoke-tested (steps 3-4 of 10):\n\n"
    "- `pipeline/analyze.py`: runs all seven tasks per message (summary, extraction, "
    "intent+urgency, routing, sentiment, translation, draft reply), persists each result "
    "to sqlite `analysis` with its provenance (`mock | llm | fallback`) and model, and "
    "caches so a message is only analysed once.\n"
    "- New endpoints: `GET /api/queue?mode=1` (the inbox re-ordered by AI urgency, with "
    "the routed team per message), `GET /api/messages/{id}?mode=1` (message + the whole "
    "analysis bundle), `POST /api/analysis/{id}?force=` (re-run), corrections "
    "(`POST/GET/DELETE /api/corrections`), and `GET /api/accuracy` (per-task accuracy "
    "against the day's ground truth, corrected for a person's edits — a correction to "
    "null is honoured as \"no value\").\n"
    "- Offline smoke (`tools/smoke_mode1_api.py`): 60 messages, mode-0 queue unchanged, "
    "m37 = Eleanor Voss, urgent hardship 5, routed to escalations; mode-1 queue sorted "
    "by urgency; corrections round-trip; accuracy across the day: 0.95 extraction, "
    "0.88 intent, 0.83 routing.\n\n"
    "Next: the front end — mode-1 transcript with confidence spans, the AI panels with "
    "provenance badges, editable fields that log corrections, the m37-style re-sort "
    "animation, and the scoreboard's accuracy view. Then full pytest + chromium smoke, "
    "then push. (Still planning the push together with Mode 2's gate so the review gets "
    "a complete milestone.)"
)

req = urllib.request.Request(
    "https://agent-tickets.fraying.win/api/tickets/fancy-wombat/comments",
    data=json.dumps({"body": body}).encode(),
    method="POST",
    headers={
        "Authorization": f"Bearer {os.environ['HEARTHBOARD_TOKEN']}",
        "Content-Type": "application/json",
        "User-Agent": "overheard-rezkin/1.0",
    },
)
print(urllib.request.urlopen(req).read().decode()[:300])
