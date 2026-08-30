# Pre-existing work disclosure

Required by ground rule 02: make clear what existed before the competition and what was added.

## Timeline

The project started **18 Sept 2025** as a three-person side project and was actively developed
until **March 2026**, then dormant. The competition window opened **28 Aug 2026 15:00 UTC**.
Everything below the second heading was written after that timestamp.

## Git history disclosure

> This repository was created on 30 Aug 2026 from a tree that was never under version control.
> Its history is reconstructed: each commit holds the final state of the files it touches, and
> commit dates are assigned, not observed. The order is real; the dates are not. `PROGRESS.md`
> timestamps are real.

Read the boundary above from this file and from `PROGRESS.md`, not from `git log`. The first
commit imports `legacy/` and is dated before the competition window opened, which reflects when
that code existed, not when it was committed here.

## Existed before the competition

- Anonymous Twitch IRC chat ingestion and persistence
- streamlink + ffmpeg audio extraction; Deepgram Nova-3 streaming transcription with diarization
- Periodic frame extraction and captioning against a local VLM endpoint
- Rolling two-minute stream context from speech + frame captions
- Per-message reason/category generation (the seven-category taxonomy)
- Hierarchical summaries at 1m / 5m / 30m / 2h
- A static dashboard shell driven entirely by generated placeholder data
- Exploratory notebooks (LangGraph tutorial, embedding probes)

That code is preserved under `legacy/` for reference. **It is not imported by the submission**,
and no file in `src/`, `evals/` or `tests/` reads from it.

One exception, and it is deliberate: `legacy/frontend/` was **removed from the tree on
2026-08-30** (RISKS #13). It was a static dashboard shell driven entirely by generated
placeholder data — `chat-simulator.js`, `messageGenerator`, `Math.random` across six files
including its `index.html`. Shipping fabricated data inside a submission whose whole argument is
"never present generated data as real" was the wrong trade for 180 KB of reference material. It
remains in this repository's git history, and it is still disclosed above as prior work; it is
simply not part of what is submitted.

The prior work contributes ideas — the five card types map onto the old seven-category taxonomy,
and the deterministic reducer is the January 2026 cost finding turned into a component — but not
code.

## Added during the competition

Each item below exists in the tree and is covered by tests; `DECISIONS.md` carries the rationale
for every non-obvious choice, and `PROGRESS.md` records what was attempted per session.

**Determinism spine**
- `Clock` abstraction; event contract with content-derived ids; replay loader
- Content-addressed model-call cache with `replay` / `record` / `live` modes, where a replay miss
  is a hard error rather than a silent API call
- Trace ids derived from `(agent, case_id)` instead of `uuid4`, so a published run document is
  byte-identical across replays

**Ingestion**
- Fixture recorder (capture stage, no keys) and the two-stage capture → enrich split
- Deepgram and vision enrichment paths, both routed through the cache, both keyed on a media
  digest so the committed cache holds no audio or base64

**Systems under comparison**
- Single-prompt baseline and the chat-only diagnostic ablation
- Deterministic reducer, bounded read-only tools, and the audience-signal agent loop
- Deterministic provenance gate and explicit abstention

**Measurement**
- Evaluation harness, gold labels, scorer, and the frozen case set
- Both systems scored on every emitted card, and fixture provenance printed alongside every
  results table

**Artifacts**
- Post-stream debrief, derived entirely from gate-verified cards with no model call
- Operator dashboard written fresh, rendering only served replay output
- Trajectory writer, writing as the work happens
- Packaging (`pyproject.toml`) so the documented commands run from a clean clone
