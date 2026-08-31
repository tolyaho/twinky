# Coding-agent disclosure

What was used to build this, during the competition window that opened **28 Aug 2026 15:00 UTC**.
Work before that timestamp is listed in `docs/PRE_EXISTING.md`.

## Tools

| Tool | Version | Used for |
|---|---|---|
| Claude Code (CLI) | 2.1.246 | The whole competition-window build: implementation, tests, docs, and the review that found the defects listed below. Verified with `claude --version`. |
| Claude Opus 5 (1M context) | `claude-opus-5[1m]` | The model behind those Claude Code sessions. |
| Tooling used before 28 Aug 2026 | `[TBD]` | Not known to the competition-window sessions. The original three-person project ran Sept 2025 – Mar 2026; the author must fill this in. |

No coding agent was given credentials, network write access, or permission to push. Nothing in
this repository was committed or published by an agent.

## How the work was actually run

An unattended loop, one bounded unit of work per iteration. The cadence moved with the deadline —
30 minutes, then 10 through the night, back to 30, and 20 for the last stretch; **109 iterations
are logged**, of which 61 carry a `## Iteration` heading in `PROGRESS.md` and the remainder are
recorded in `DECISIONS.md` and the commit history. The loop specification changed as the work did
— `NIGHT_LOOP.md`, then `FIX_AND_FINISH.md`, then `LOOP_FINAL.md`, then a version led by
`RENAME.md`, and finally `AGENT_FIX.md` — and each lives one directory up, outside this
repository.

Each iteration:

1. Read the progress log and the cost ledger.
2. Take the topmost unfinished item on a fixed ladder. If it is blocked, record the blocker in
   `RISKS.md` and take the next unblocked item.
3. Do that one thing.
4. Run `make test`. If tests fail, fixing them is the next iteration's only task.
5. Append to `PROGRESS.md`; add any decision to `DECISIONS.md`.

The loop prompts are the specification the sessions were run against, including the budget
guardrails. Those guardrails held: **every paid call is itemised in `COST_LEDGER.md`, nine entries
totalling $0.4364** against a $5.00 hard cap, and `TS_LLM_MODE=replay` — where a cache miss raises
rather than calling an API — was the default in every other iteration.

## Where the evidence is

There is no exported chat transcript. The written record is in-tree and was produced as the work
happened rather than reconstructed afterwards:

| File | What it records |
|---|---|
| `PROGRESS.md` | append-only, one block per iteration: attempted, result, next, blockers |
| `DECISIONS.md` | every scope or technical decision with its rationale |
| `RISKS.md` | anything that could fail the qualification gate, with status |
| `COST_LEDGER.md` | every paid call, with a running total |

## What the agent sessions found, not just built

Listed because a disclosure that only claims productivity is not a disclosure. Each was found by
running the thing rather than reading it, and each is recorded in `DECISIONS.md` or `RISKS.md`:

- `make scan` reached neither `.env` nor `legacy/`, and matched its own pattern list, so the
  secret gate had never been meaningful (RISKS #18). Rewriting it surfaced two P0 credential
  leaks (#16, #17).
- `python -m ts.cli` failed from a clean clone — every documented command died with
  `ModuleNotFoundError` (RISKS #10).
- Trace ids came from `uuid4`, so two replays of one fixture produced different published
  documents.
- The test suite wrote 55 trajectories into this deliverable directory, with case ids no
  evaluation case has.
- The debrief's "recurring themes" section counted words out of model-written titles, so it
  returned "chat", "says" and "the".
- **The first measured evaluation was invalid and was thrown away.** The baseline had been handed
  the agent's tool-calling prompt, so it answered with a tool call, the parser turned that into an
  empty list, and it scored zero cards across all eleven cases. `make eval` now prints
  `BROKEN — NOT A RESULT` and exits 5 if any system emits nothing, because that failure looks
  exactly like a result.
- **Keyless reproduction was silently broken.** The default text model was one the runs had never
  been recorded with, so `make eval` reproduced only inside the author's environment — which is
  nobody who scores this.
- **All three systems were citing timestamps as event ids**, because the prompt rendered chat
  lines led by `[1788074707878]` and never labelled the id.
- **`make replay` typed with no arguments exited 3** on committed state, while `README.md`
  promised that exact command runs with no keys.
- **`make scan` could never pass on a developer machine**, failing on a git-ignored `.env` that
  `make archive` provably cannot include. A security check that always fails is one nobody reads.
- **The agent had never once read the screen.** Counted from the cache: across 70 recorded
  conversations, chat appeared in 70 and frame captions in 2, and all 57 of the agent's own
  opening turns contained zero event ids — so citing a chat message was the only move available
  to it. That diagnosis produced a fix, a measurement, and a decision not to adopt it.
- **A moderation rule flagged the product's own best output.** Coordinated-repeat detection, built
  exactly as specified, marked `ranger` from 15 accounts as suspicious — which is the audience
  signal the board exists to surface.
- **The shot list, README, SUBMISSION and architecture diagram had all drifted** from the built
  product, in one case describing a two-column page that had not existed for fifteen iterations.
  Each now has a test that fails when it drifts again.

## Product-agent trajectories

Separate deliverable, separate directory: `../product-agent/`. Written automatically by
`ts.workflow.trace` during every run, never hand-authored. **118 trajectories** across the agent,
the single-prompt baseline and the chat-only ablation, each written as the run happened rather
than reconstructed afterwards. Trace ids derive from `(agent, case_id)`, so they are stable across
re-runs — a deliberate fix after `uuid4` made two replays of one fixture produce different
published documents.

*(This section previously read "empty today because no run has been recorded yet". That was true
when it was written and stopped being true at the first recorded run; it is corrected here rather
than quietly overwritten, because a disclosure that silently repairs its own errors is not one.)*

## Scale, for calibration

| | |
|---|---:|
| Commits in the competition window | 171 |
| Iterations logged | 109 |
| Decisions recorded with rationale | 437 |
| Risks tracked | 51 |
| Tests | 709 |
| Total spend on model calls | $0.44 |
