# Decisions

Every scope or technical decision, with a one-line rationale. This file is the raw material for
`docs/IMPROVEMENT_CHANGELOG.md` — write entries as decisions are made, not afterwards.

| Date | Decision | Rationale |
|---|---|---|
| 2026-08-29 | Replay is the graded path; live is demo-only | Live streams are not reproducible; judges cannot re-run a broadcast |
| 2026-08-29 | Content-addressed model-call cache, committed | Lets judges reproduce every number with no API keys and zero cost |
| 2026-08-29 | Two primary metrics instead of a composite GS-F1 | A 4-clause matching rule is unstable on 12 cases and illegible in a 5-minute video |
| 2026-08-29 | Unsupported-card rate as a primary metric | Deterministically checkable with no gold labels, so it scales to every fixture |
| 2026-08-29 | Baseline receives the same raw multimodal events | Comparing against chat-only would measure extra data, not the agentic workflow |
| 2026-08-29 | One agent, bounded tools; no web-search or scheduler agent | Neither addresses a demonstrated failure; PDF states purposeful choices beat component count |
| 2026-08-29 | Dashboard is the landing page | Halves the frontend work and feeds End-to-End Quality instead of competing with it |
| 2026-08-29 | API-only, `deepseek-v4-flash` | No local compute available; `deepseek-chat` retired 2026-07-24 |
| 2026-08-29 | Cache key names media by SHA-256; bytes never enter the entry | The cache is committed for keyless reproduction — a 19 MB WAV or 100 KB of base64 per frame does not belong in git |
| 2026-08-29 | Deepgram via REST + `httpx`, no SDK | `httpx` is already a dependency; an SDK would add a version surface for one POST |
| 2026-08-29 | Frame prompt written fresh, not ported from `legacy/.../image_annotations/workers.py` | The loop's context guardrail allows only three legacy files; the intent (factual, ≤500 chars, "text unclear" over invention) was already recorded in the enrich docstring |
| 2026-08-29 | Enrichment writes rows without `id`; the replay loader derives them | One implementation of the id rule, so the writer and reader cannot drift; `EventIndex` already rejects duplicates |
| 2026-08-29 | Deepgram `utterances` preferred, word-grouping only as fallback | Deepgram's own final segmentation beats a hand-tuned pause threshold, and the fallback keeps enrichment working if the flag is ever dropped |
