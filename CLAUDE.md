# CLAUDE.md — read this before touching anything

Twinky links each cluster of live chat to the stream moment that caused it, and shows the
evidence. Start with `PRODUCT_v2.md` — it is the product definition this repository serves,
reconstructed from the team's own record. `notes/` holds the working strategy notes.

## Product invariant — do not drift

> Twinky turns an unreadable live chat into a small number of verified audience signals:
> it links each cluster of answers, reactions, questions and warnings to the exact stream moment
> that caused it, and shows the evidence.

If a change does not strengthen
`multimodal stream context -> grounded audience signal -> evidence -> streamer action`,
it is out of scope. Say so and drop it.

The loop that invariant serves: **readable chat → worth writing in → livelier stream → more
views.** The board goes on stream, visible to viewers. That is the product's own goal, not a
marketing line.

## Hard rules

1. **Never fabricate.** No invented commit SHAs, metrics, benchmarks, citations or file paths.
   If it was not measured, it does not go in a document. Unverifiable external facts get marked
   `UNVERIFIED` in `RISKS.md`.
2. **Never present generated data as real.** The first implementation's frontend fabricated
   names, emotes, summaries and cluster values, and it was deleted for it. Anything shipped must
   render real replay output or be visibly labelled a placeholder.
3. **No secrets.** `.env.example` holds placeholder names only. Never commit keys, tokens, DB
   credentials, the Telegram export, or traces containing any of them.
4. **Evidence over features.** Forced to choose: measurement over capability, replay over live,
   one instrumented agent over five theatrical ones.
5. **Human approval on outward actions.** Polls, highlights and replies stay drafts.
6. **Write traces as work happens.** Reconstructing them at the end is dishonest.
7. **Every number in a document is reproduced by a command.** `make eval` is the arbiter. A
   change to a published figure that does not come with a re-run is a regression in itself.

## Determinism is the architecture

Replay must be bit-reproducible. That means:

- Never call `time.time()` or a bare `now_ms()` in a query path. Take a `Clock` (`ts.clock`).
- Never batch or window on wall-clock age. Batch on `(ts_ms, event_id)`.
- Never use unseeded `random` in an evaluated path.
- `temperature=0` for anything evaluated.
- Order every query that feeds a prompt explicitly by `(ts_ms, event_id)`.
- All model calls go through `ts.cache.CachedProvider`. In `replay` mode a cache **miss is a hard
  error**, never a silent API call.

`notes/04-CODE_AUDIT.md` lists the specific landmines in the first implementation. Read it before
porting anything from `reference/`.

## `reference/` is for reading

`reference/` is the original repository (Sept 2025 – Mar 2026). It is not imported at runtime and
it is not off limits: it holds the working ancestor of `memory`, `stream context` and `image
annotations`, and the reason taxonomy in
`reference/src/parsers/message_reasons/prompts/general.txt` is the origin of the card types.
Read it before changing `src/ts/provenance.py`.

## State files — update every session

- `docs/IMPROVEMENT_CHANGELOG.md` — the engineering log; update as work happens, never at the end
- `RISKS.md` — anything that could fail in the open, with status
- `docs/archive/` — `PROGRESS.md` and `DECISIONS.md`, the record of how this was built. Append to
  `DECISIONS.md` when a scope or technical decision is made.

## Commands

```
make setup      # venv + deps
make test       # unit tests, no network, no keys
make capture    # capture a fixture from a live channel   (needs API keys)
make enrich     # add speech and captions to a fixture    (needs API keys)
make replay     # run the agent over a fixture            (no keys, cached)
make baseline   # run the single-prompt baseline          (no keys, cached)
make eval       # score all arms, write evidence/
make demo       # serve the dashboard on replay output
make scan       # secret scan
```

`make test`, `make replay`, `make baseline` and `make eval` must work with **no API keys**.
That property is what makes every claim here checkable for free — do not break it.

## Layout

```
src/ts/
  clock.py        Clock / WallClock / FixtureClock
  events.py       Event contract + normalization
  cache.py        content-addressed model-call cache
  providers/      text / vision / stt adapters behind interfaces
  ingest/         capture (live -> fixture) and replay (fixture -> events)
  workflow/       reduce -> tools -> agent -> provenance -> trace
  baseline/       single-prompt baseline + chat-only ablation
  report/         board, debrief, poll draft, served pages
evals/            cases, gold labels, scorer
notes/            working strategy notes
reference/        the first implementation — read it, do not import it
docs/archive/     PROGRESS.md, DECISIONS.md, and the reset plan that produced this layout
```

## Models (API only — no local compute)

- Text/JSON/tools: `gpt-4.1-nano`. Chosen for latency (1–3 s against 10–30 s), not cost.
- Vision: `gpt-4.1-mini`. STT: Deepgram Nova-3, `record` mode only.
- Replay mode calls no provider at all.

Providers sit behind adapters. If a model fails schema compliance on the eval, swap the model —
do not bend the product around it.
