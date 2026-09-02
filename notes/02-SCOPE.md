# Scope, order of work, and when to stop building

## Reality check

~30 working hours, solo. The prior planning documents were scoped for roughly ten days. This is
the version that fits.

## Priority ladder — top unfinished item only

**P0-1 Determinism spine.** Clock abstraction; event contract; replay loader; fix the landmines
in `04-CODE_AUDIT.md`. *Nothing downstream works without this.*

**P0-2 Model-call cache.** Content-addressed, three modes, `replay` is default and a miss is a
hard error. *This is what lets anyone reproduce with no API keys and zero cost.*

**P0-3 Fixtures.** 3 × ~10 min. At least one self-streamed with scripted ground truth.
**Time-critical — needs streams live tonight.**

**P0-4 Baseline.** One direct prompt, same raw events, same schema, no tools/state/verifier.
Plus a chat-only ablation as a diagnostic. Freeze the numbers before touching the agent.

**P0-5 Evaluation.** 10–12 cases, two primary metrics (see `03-EVAL_DESIGN.md`).

**P0-6 Agent.** Reducer → bounded tools → one signal agent → provenance gate → trace writer.

**P0-7 UI on real data.** Rip out the random generators.

**P0-8 Deliverables.** All four. Incomplete = rejected.

## Cut list — do not build

Web-search agent; scheduler agent; giveaways; social graph / streamer map; custom embedding
training; RAG for architectural beauty; auto-posting or moderation; multi-channel; viewer-facing
character bot; separate marketing site; long-term memory before it is proven useful; any invented
live metric.

Keeping the March architecture diagram in the README with implemented nodes marked, plus one
sentence on why the rest was scoped out, **scores points** — the challenge PDF states that
purposeful choices matter more than component count.

## Schedule

| When | Work | Done means |
|---|---|---|
| Sat evening | P0-1, P0-2, P0-3 | `make replay` runs a fixture end to end, deterministically, offline |
| Sunday AM | P0-4, P0-5 | Baseline numbers frozen in `evidence/` |
| Sunday PM | P0-6 | Agent beats baseline on both metrics; traces written |
| Sun evening | P0-7 | Dashboard renders real cards; screen-capture taken |
| **Sun 20:00 MSK** | **Decision gate** | If P0-1..6 are not green: stop building, ship what exists |
| Monday AM | Clean-room run, changelog, reproduction guide | A second machine reproduces the numbers |
| Monday PM | Video cut, archive, upload | **Submitted by 19:00 MSK — two hours of slack** |

If you fall behind, protect the demo: a product nobody can watch running cannot be assessed at
all, by anyone.

## Minimum viable submission

In order of what to save last: replay + baseline + agent on 6 cases + both metrics + changelog +
reproduction guide + 5-minute video + traces. Everything else is optional.

## The rule when torn

Evidence over features. Replay over live. One instrumented agent over five theatrical ones.
Real evidence-linked UI over a beautiful landing page.
