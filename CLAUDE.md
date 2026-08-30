# CLAUDE.md — read this before touching anything

Hackathon submission for the micro1 Frontier Engineering Challenge 2026.
**Deadline: Mon 31 Aug 2026, 18:00 UTC / 21:00 MSK.** Late or incomplete entries are rejected.
Only the latest *complete* submission is evaluated.

Strategy notes live in `../notes/`. Read `../notes/01-PRODUCT.md` and `../notes/02-SCOPE.md`
before proposing anything. The build loop is `../LOOP_PROMPT.md`.

`../notes/` is an internal working directory and is deliberately **not** part of this repository —
its own index says it never ships. Every `../notes/...` path below and in `RISKS.md`,
`evals/DATA.md`, `evals/scorer.py` and `legacy/README.md` therefore resolves only in the author's
tree. Nothing in `src/`, `tests/` or `evals/` reads from it, so a clone is complete and
`make test` is unaffected.

## Product invariant — do not drift

> Twitch Agent turns an unreadable live chat into a small number of verified audience signals:
> it links each cluster of answers, reactions, questions and warnings to the exact stream moment
> that caused it, and shows the evidence.

If a change does not strengthen
`multimodal stream context -> grounded audience signal -> evidence -> streamer action`,
it is out of scope. Say so and drop it.

## Hard rules

1. **Never fabricate.** No invented commit SHAs, metrics, benchmarks, citations or file paths.
   If it was not measured, it does not go in a document. Unverifiable external facts get marked
   `UNVERIFIED` in `RISKS.md`.
2. **Never present generated data as real.** The legacy frontend fabricates names, emotes,
   summaries and cluster values. Anything shipped must render real replay output or be visibly
   labelled a placeholder.
3. **No secrets.** `.env.example` holds placeholder names only. Never commit keys, tokens, DB
   credentials, the Telegram export, or traces containing any of them.
4. **Evidence over features.** Forced to choose: measurement over capability, replay over live,
   one instrumented agent over five theatrical ones.
5. **Separate pre-existing from new.** Work before 28 Aug 2026 15:00 UTC is pre-existing and must
   be labelled as such. Competition iterations are only those measured on the frozen eval set.
6. **Human approval on outward actions.** Polls, highlights and replies stay drafts.
7. **Write traces as work happens.** Reconstructing them at the end is a gate risk and dishonest.

## Determinism is the architecture

Replay must be bit-reproducible. That means:

- Never call `time.time()` or a bare `now_ms()` in a query path. Take a `Clock` (`ts.clock`).
- Never batch or window on wall-clock age. Batch on `(ts_ms, event_id)`.
- Never use unseeded `random` in an evaluated path.
- `temperature=0` for anything evaluated.
- Order every query that feeds a prompt explicitly by `(ts_ms, event_id)`.
- All model calls go through `ts.cache.CachedProvider`. In `replay` mode a cache **miss is a hard
  error**, never a silent API call.

`../notes/04-CODE_AUDIT.md` lists the specific landmines in the legacy code. Read it before
porting anything from `legacy/`.

## State files — update every session

- `PROGRESS.md`  append-only: what was attempted, result, next step
- `DECISIONS.md` every scope/technical decision with a one-line rationale (feeds the changelog)
- `RISKS.md`     anything that could fail the qualification gate, with status
- `docs/IMPROVEMENT_CHANGELOG.md` the deliverable — update as work happens, never at the end

## Commands

```
make setup      # venv + deps
make test       # unit tests, no network, no keys
make record     # capture a fixture from a live channel   (needs API keys)
make replay     # run the agent over a fixture            (no keys, cached)
make baseline   # run the single-prompt baseline          (no keys, cached)
make eval       # score both, write evidence/comparison.csv
make demo       # serve the dashboard on replay output
```

`make test`, `make replay`, `make baseline` and `make eval` must work with **no API keys**.
That property is the reproducibility story — do not break it.

## Layout

```
src/ts/
  clock.py        Clock / WallClock / FixtureClock
  events.py       Event contract + normalization
  cache.py        content-addressed model-call cache
  providers/      text / vision / stt adapters behind interfaces
  ingest/         record (live -> fixture) and replay (fixture -> events)
  workflow/       reduce -> tools -> agent -> provenance -> trace
  baseline/       single-prompt baseline + chat-only ablation
  report/         post-stream debrief
evals/            cases, gold labels, scorer
legacy/           previous repo, reference only — do not import from it
```

## Models (API only — no local compute)

- Text/JSON/tools: `deepseek-v4-flash`. **`deepseek-chat` was retired 2026-07-24 — never use it.**
- Escalation: `deepseek-v4-pro`, only if the eval shows it earns its cost.
- Vision: `deepseek-v4-flash-vision-exp` or another hosted VLM. **V4-Flash is text-only.**
- STT: Deepgram Nova-3 streaming, `record` mode only.
- Replay mode calls no provider at all.

Providers sit behind adapters. If a model fails schema compliance on the eval, swap the model —
do not bend the product around it.
