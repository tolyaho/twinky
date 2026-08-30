# Trajectories

Required deliverable: representative, readable trajectories for **every agent used** — both the
agent inside the product and the coding agents used to build it.

## Product agent — `product-agent/`

One file per evaluation case, written automatically by `ts.workflow.trace` during every run.
Never hand-author them: reconstructing a trajectory after the fact is a qualification-gate risk
and dishonest.

Each is followable from instructions to final result and shows: agent instructions · what the
agent did · how each tool responded · the feedback that shaped the next step · retries ·
provenance-gate decisions · human checkpoints.

**Status: empty.** No fixture has been recorded, so no real run exists yet (`RISKS.md` #2). The
directory previously held 55 files, all of them test artifacts with case ids like `t3` that no
evaluation case has; they were removed on 2026-08-30 and the suite now writes to a temporary
directory via `TS_TRACE_DIR`. A graded deliverable holding regenerable test output misrepresents
the work.

Three trajectories are required at minimum, one per system under comparison:

| System | Agent name in the trace | Status |
|---|---|---|
| Final workflow | `audience_signal_agent` | `[TBD]` — needs a recorded fixture |
| Single-prompt baseline | `baseline_single_prompt` | `[TBD]` |
| Chat-only ablation | `baseline_chat_only` | `[TBD]` |

## Coding agents — `coding-agents/`

Disclosure of the tools used to build this project, the method they were run under, and where
the written record lives. See `coding-agents/README.md`.

## Redaction

Strip API keys, tokens and personal data before committing — without making the trace
unintelligible. Run `make scan` afterwards; it walks dotfiles and `legacy/` too.
