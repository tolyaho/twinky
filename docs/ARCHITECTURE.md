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
   the dashboard    post-stream debrief   trace writer
   ✔ report/serve.py ✔ report/debrief.py      ✔ workflow/trace.py → trajectories/
   + static/
```

The reporting layer is a second, wholly deterministic pipeline over the same events. It calls no
model — with exactly one cosmetic exception, marked below — so everything it draws holds up in a
live session with no key at all.

```
  normalized event stream
          │
   deterministic grouping        ✔ workflow/reduce.py   group_chat: reaction wave,
          │                                             4-char prefix, content token
          ├──▶ the board          ✔ report/board.py     rows: a trigger and the groups that
          │                                             followed, `matched` or `preceding`
          ├──▶ the rail           ✔ report/board.py     rate, chatters, concentration,
          │                                             questions, the gate ledger by code
          ├──▶ questions to you   ✔ report/board.py     answered by reading the transcript
          │                                             AFTER the question was asked
          ├──▶ NEEDS A LOOK       ✔ report/moderation.py  links, coordinated repeats, prompt
          │                                               injection — read-only, no action
          ├──▶ group labels       ✔ report/labels.py    the ONE model call here. Cosmetic,
          │                                             never evidence; falls back to the token
          └──▶ agent graph        ✔ report/graph.py     generated from the code it describes

   the same grouping, live       ✔ live_chat.py         Tier 0: anonymous IRC, no key, no model,
                                                        no cost — and no cause, and it says so
   the full pipeline, live       ✔ live.py              paid, capped, time-limited, temp cache
```

Cutting across all of it:

| Concern | Where | Status |
|---|---|---|
| Model-call cache — the reproducibility spine | `cache.py` | ✔ three modes; a replay miss raises |
| Clock abstraction — no wall-clock in a query path | `clock.py` | ✔ |
| Provider adapters — text, vision, STT behind interfaces | `providers/` | ✔ |
| Evaluation harness, gold labels, scorer | `evals/` | ✔ harness; 11 frozen cases on real captures |
| Secret gate | `scripts/scan_secrets.py` | ✔ passes on a git-ignored `.env`, fails on anything shippable |
| Grouping evaluation — pair precision/recall on frozen labels | `evals/grouping/` | ✔ arms A, B and C measured; labels frozen in a commit with no arm code |

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
module implements it and no evaluation case needs it: the fixtures run 2–12 minutes and the
analysis windows are sixty seconds. It stays here as a named gap rather than an implied feature.

**Live capture is demo-only.** The graded path reads a fixture. Live streams are not
reproducible, and judges have no API keys.

## What each implemented component is for

| Component | The observed failure it fixes |
|---|---|
| Speech + frame context | Short chat replies are meaningless as text (Sept 2025 – Jan 2026) |
| Event-centric grouping | Embedding clustering gave unstable clusters (Oct 2025; again Mar 2026 — and re-measured here in Aug 2026, where one threshold scored F1 0.770 on one window and precision 0.164 on another) |
| Group labels, cosmetic only | `violet × 27` is a token, not a meaning — and a caption that could break the page is not worth having |
| Read-only moderation | Chat is untrusted data; an attempt to instruct the system is worth surfacing, and acting on it is not this build's decision |
| Deterministic reducer | Per-message inference was too slow and too expensive at scale (Jan, Mar 2026) |
| Provenance gate + abstention | Cards attaching to nothing, in the team's own testing 4 Jan 2026 |
| Replay + response cache | Live streams are not reproducible and judges have no API keys |
