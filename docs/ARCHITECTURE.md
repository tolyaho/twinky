# Architecture

Every node below is marked with what actually exists in the tree. A diagram that shows a design
rather than a build is worth nothing to a reviewer who opens `src/`.

## The graded path

```
  capture (live, no keys)          enrich (keys, once per fixture)
  chat + audio + frames  ──────▶   transcript.jsonl + frames.jsonl
        │                                     │
        └────────────── fixture ──────────────┘
                            │
                    replay loader                 ✔ ingest/replay.py
                            │
                  normalized event stream         ✔ events.py  (total order on ts_ms, event_id)
                            │
                  deterministic reducer           ✔ workflow/reduce.py  (dedup, counts kept)
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
  bounded context tools  ✔ workflow/tools.py  │   single-prompt baseline  ✔ baseline/
          │        (4 read-only, time-capped) │        (same events, same schema, no tools)
          │                                   │
  audience signal agent  ✔ workflow/agent.py  │
   (one agent, max_steps=4, strict JSON)      │
          └─────────────────┬─────────────────┘
                            │
                  provenance gate               ✔ provenance.py  (deterministic; rejects
                            │                                      unsupported cards)
          ┌─────────────────┼─────────────────┐
          │                 │                 │
   live rail        post-stream debrief   trace writer
   ✔ report/serve   ✔ report/debrief      ✔ workflow/trace.py → trajectories/
   + static/
```

Cutting across all of it:

| Concern | Where | Status |
|---|---|---|
| Model-call cache — the reproducibility spine | `cache.py` | ✔ three modes; a replay miss raises |
| Clock abstraction — no wall-clock in a query path | `clock.py` | ✔ |
| Provider adapters — text, vision, STT behind interfaces | `providers/` | ✔ |
| Evaluation harness, gold labels, scorer | `evals/` | ✔ harness; 4 of 12 cases |
| Secret gate | `scripts/scan_secrets.py` | ✔ |

## Designed, deliberately not built

**The March 2026 north star.** An orchestrator fanning out to a data-pulling agent, a web-search
agent, a scheduling agent that re-injects its own queries, a save-memory agent, and stream action
tools.

Scoped out on purpose. Web search and scheduling address no failure observed in the evaluation,
and each would add trajectories, failure modes and demo complexity without measured benefit. The
challenge PDF states that purposeful choices matter more than component count.

Of that design, what survived: data-pulling became four bounded read-only tools, and a
verification stage was added that the original sketch did not have.

**The summary hierarchy — 1m / 5m / 30m / 2h — is NOT built.** It is the answer to "a six-hour
stream does not fit one context window", and it is genuinely part of the product thesis, but no
module implements it and no evaluation case needs it: the fixtures are ten minutes and the
analysis windows are sixty seconds. It stays here as a named gap rather than an implied feature.

**Live capture is demo-only.** The graded path reads a fixture. Live streams are not
reproducible, and judges have no API keys.

## What each implemented component is for

| Component | The observed failure it fixes |
|---|---|
| Speech + frame context | Short chat replies are meaningless as text (Sept 2025 – Jan 2026) |
| Event-centric grouping | Embedding clustering gave unstable clusters (Oct 2025; again Mar 2026) |
| Deterministic reducer | Per-message inference was too slow and too expensive at scale (Jan, Mar 2026) |
| Provenance gate + abstention | Cards attaching to nothing, in the team's own testing 4 Jan 2026 |
| Replay + response cache | Live streams are not reproducible and judges have no API keys |
