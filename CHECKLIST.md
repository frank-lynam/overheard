# Goal

fancy-wombat handed back to review: frank's "ready to close?" answered, E501 fixed, branch pushed, status set to review, phase-6 work proposed as a ticket.

## How it works

Ticket fancy-wombat is in_progress, mine. All 3 modes built; last commit 47e650f + checklist note ba32d66 on ticket/fancy-wombat. Frank's comment 162 asks if it's ready to close. ruff currently shows exactly one error: E501 line 144 of tools/probe_mode3_ui.py (an over-long querySelector line from view 10).

## Why it doesn't

It's not in review yet (status still in_progress, no hand-back comment), and ruff check . — which both CI and publish.yml run — would fail on that one long line.

## What would

Wrap the selector so ruff --no-fix is clean and the probe still passes; commit+push to deploy ticket/fancy-wombat; post a "Done" hand-back comment answering frank's question; PATCH status to review; POST a proposal ticket for phase 6 (release & rehearsal); update MEMORY.md; verify each with real outputs.

## Steps

- [x] 1. Fix E501 in tools/probe_mode3_ui.py:144, ruff check --no-fix clean
- [x] 2. Re-run probe_mode3_ui.py, PROBE_MODE3 OK
- [x] 3. Commit and push to deploy ticket/fancy-wombat (announce first)
- [ ] 4. Reply to frank (comment 162) with Done hand-back on the ticket
- [ ] 5. PATCH fancy-wombat status to review
- [ ] 6. Propose phase-6 release/rehearsal ticket
- [ ] 7. Update MEMORY.md, verify board state
