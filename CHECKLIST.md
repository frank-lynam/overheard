# Goal

Mode 3 view 8 (knowledge-gap mining) live end to end: an analytics module that cross-references archive contacts against kb_articles topics, ranks the questions callers ask often that no article answers, drafts FAQ and IVR text for each gap (plain code), a GET route, a mode-3 pane, and tests that recover the planted 22-B and 1099 gaps.

## How it works

Verified: generator.py KB (lines 29-38) has 8 articles, topics = JSON list of driver ids they cover; comment marks PLANTED gaps (22-B re-verification, fax number, 1099 vendor change). contacts table carries root_cause; kb_articles table exists (db.py:18) but nothing reads it yet. Real seed: 32,211 of 71,788 archive contacts (45%) have no covering article; form-22b-confusion (4,807) and tax-form-1099 (801) are the planted ones. Established pattern from views 4-7: analytics module -> route in routes.py -> .m3-pane in index.html + render fn in mode3.js + lazy block in main.js + css -> pytest -> ruff --no-fix -> full pytest -> probe+shot -> commit/push -> board comment.

## Why it doesn't

No analytics module reads kb_articles; no /api/knowledge-gaps route; index.html has 7 of 8 mode-3 panes (no knowledge-gaps section); no tests. The planted gaps live only in generator comments + the topics column.

## What would

analytics/knowledge_gaps.py: load KB topics; per-driver contact totals (count, handle, resolve rate); gaps = drivers with no covering article, ranked by count; weak coverage = covered drivers whose real phrasings use content words the article body never mentions (catches the planted fax-number gap: kb-documents says 'Mail documents...' and never says fax); FAQ draft per gap (title = a real caller phrasing, body = plain-code answer from the driver's data) and a short IVR line. GET /api/knowledge-gaps in routes.py. Pane .m3-pane.knowledge-gaps in index.html + renderKnowledgeGaps in mode3.js + lazy block in main.js + css. Tests: form-22b-confusion is the #1 gap, tax-form-1099 flagged, covered driver payment-status is NOT a gap, fax word surfaces as weak coverage of kb-documents, FAQ drafts non-empty, API 200. Ruff --no-fix, full pytest, extend probe + screenshot (real repo path), commit + push (announce), board comment + attachment, tick checklist.

## Steps

- [x] 1. analytics/knowledge_gaps.py (gap ranking + weak coverage + FAQ/IVR drafts)
- [x] 2. GET /api/knowledge-gaps route
- [x] 3. Mode-3 pane: index.html + api.js + mode3.js + main.js + css
- [x] 4. pytest: planted 22-B gap #1, 1099 flagged, covered driver not a gap, fax weak coverage, API 200
- [x] 5. ruff --no-fix + full pytest green
- [x] 6. extend chromium probe: knowledge-gaps pane + screenshot
- [ ] 7. commit + push
- [ ] 8. board comment with report + screenshot
