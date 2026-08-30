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

Unattended loop, one bounded unit of work every 30 minutes:

1. Read the progress log and the cost ledger.
2. Take the topmost unfinished item on a fixed ladder. If it is blocked, record the blocker in
   `RISKS.md` and take the next unblocked item.
3. Do that one thing.
4. Run `make test`. If tests fail, fixing them is the next iteration's only task.
5. Append to `PROGRESS.md`; add any decision to `DECISIONS.md`.

The loop prompt itself lives outside this repository, one directory up, as `NIGHT_LOOP.md`. If
the submission archive should contain it, copy it in — it is the specification the sessions were
run against, including the budget guardrails that kept paid calls at zero through the offline
phase.

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

## Product-agent trajectories

Separate deliverable, separate directory: `../product-agent/`. Written automatically by
`ts.workflow.trace` during every run, never hand-authored. It is **empty today** because no run
has been recorded yet — see `RISKS.md` #2.
