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

**Status: 33 real trajectories — 11 frozen cases × 3 systems**, written during the measured run
of 2026-08-30 and reproducible with `make eval` from the cache.

| System | Agent name in the trace | Trajectories |
|---|---|---|
| Final workflow | `audience_signal_agent` | 11 — one per case |
| Single-prompt baseline | `baseline_single_prompt` | 11 |
| Chat-only ablation | `baseline_chat_only` | 11 |

Worth opening first: `c01_word_puzzle_amethyst_*` for `audience_signal_agent`. It shows the
agent calling `group_repeated` and `get_transcript_window`, finding no speech, and returning a
`none` card that says "no clear speech or on-screen content detected" — **without ever calling
`get_frame_captions`**. That is the main failure mode in `docs/IMPROVEMENT_CHANGELOG.md`, visible
step by step rather than asserted.

The directory previously held 55 files, all test artifacts with case ids like `t3` that no
evaluation case has. They were removed on 2026-08-30 and the suite now writes to a temporary
directory via `TS_TRACE_DIR`, so regenerable test output cannot re-enter a graded deliverable.

## Coding agents — `coding-agents/`

Disclosure of the tools used to build this project, the method they were run under, and where
the written record lives. See `coding-agents/README.md`.

## Redaction

Strip API keys, tokens and personal data before committing — without making the trace
unintelligible. Run `make scan` afterwards; it walks dotfiles and `legacy/` too.
