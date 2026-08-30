# Reproduction guide

Written for a reviewer starting from a clean environment. Every step below is a command that was
actually run; where a result is not yet measured it says `[TBD]` rather than a plausible number.

## 0. What state this repository is in

Four fixtures have been captured from live broadcasts and enriched, and `cache/llm/` holds their
transcription and caption responses. Steps 1–6 work now with no keys.

The eval is recorded. `make eval` reproduces the committed results table from `cache/` with
**48 hits and 0 misses**, verified with every credential unset — no `.env`, no keys, no network.

An earlier run was discarded rather than reported: the baseline had been handed the agent's
tool-calling prompt and emitted zero cards across all eleven cases. `report.md` now prints a
**BROKEN — NOT A RESULT** banner, and `make eval` exits `5`, if any system emits nothing at all.

In `replay` mode a cache miss raises instead of silently calling an API: the command prints the
missing key and **exits `3`** rather than reaching for a provider, so a run either reproduces the
recorded result exactly or fails loudly. Editing a prompt, a model name or the temperature
changes the cache key and will produce exit `3` until the run is re-recorded — that is the
mechanism working, not a regression.

## 1. Requirements

- Python 3.10+ (developed on CPython 3.12)
- `make`
- No GPU, no local model runtime, **no API keys** for anything in steps 2–7

## 2. Setup

```bash
git clone [REPO_URL] && cd ts
make setup
```

This creates `.venv`, installs the pinned dependencies from `requirements.txt`, and installs the
package itself in editable mode so `python -m ts.cli` resolves. The replay path pulls exactly one
runtime package, `httpx`.

If `python3 -m venv` fails with an `ensurepip` error — it does on Homebrew Python 3.11 and 3.14
as installed on the development machine — create the environment another way and install the same
two lines into it:

```bash
uv venv .venv && uv pip install -r requirements.txt -e .
```

Both paths were verified to give a green suite. See `RISKS.md` #23. Do **not** copy `.env.example` to
`.env` — nothing below reads a key, and running without one is the point.

## 3. Tests

```bash
make test
```

Measured 2026-08-30: **339 passed** in under a second. No network, no keys, no cached model
responses needed — the suite fakes the provider everywhere a model would be called. The count
above is itself asserted by a test, so it cannot drift as tests are added.

## 4. Inspect a fixture

```bash
make inspect FIXTURE=evals/fixtures/sample     # or: python -m ts.cli inspect --fixture ...
```

Prints event counts, span, and the reducer's compression ratio. No model call.

## 5. Baseline

```bash
make baseline FIXTURE=evals/fixtures/[NAME]
```

Writes `evidence/raw-results/[NAME].baseline.json`. Runtime **~40 ms** on a 12-minute fixture.
Cost **$0.00** — every response comes from the cache.

Add `make ablation FIXTURE=...` for the chat-only diagnostic. It is not the headline baseline.

## 6. Final solution

```bash
make replay FIXTURE=evals/fixtures/[NAME]
```

Writes `evidence/raw-results/[NAME].agent.json` and a trajectory per window under
`trajectories/product-agent/`. Runtime **~40 ms** on a 12-minute fixture. Cost **$0.00**.

## 7. Evaluation

```bash
make eval
```

Writes `evidence/comparison.csv`, `evidence/report.md` and `evidence/predictions.json`.
Reproduces the results table in the README exactly.

Measured 2026-08-30: **79 ms, 48 cache hits, 0 misses, $0.00**, run with every credential unset.
Expected final line: `cache: {'hits': 48, 'misses': 0}  ->  evidence`. Add `--ablation` to
include the chat-only diagnostic; it is cached too and adds no calls.

`report.md` carries a **NOT A REPORTED RESULT** banner whenever any case ran against a fixture
that was not captured from a real broadcast, and lists the provenance of every fixture behind the
table. Read that banner before reading the numbers.

## 8. The post-stream artifact and the dashboard

```bash
make debrief FIXTURE=evals/fixtures/[NAME]   # writes [NAME].debrief.md next to the run
make demo    FIXTURE=evals/fixtures/[NAME]   # serves the dashboard on http://127.0.0.1:8000
```

`make debrief` makes no model call: it reorganises cards that already passed the provenance gate.
The dashboard renders only what `/api/replay` serves — there is no generator and no sample data
in it, and a test fails the build if one appears.

## 9. Why this needs no keys

Every model call in the system goes through one function, `ts.cache.ResponseCache.call`, which
hashes the full request — model, the entire message list, temperature, max_tokens,
response_format — and looks it up under `cache/llm/`. Three modes, selected by `TS_LLM_MODE`:

| mode | behaviour |
|---|---|
| `replay` (default) | cache hit required; **a miss raises** |
| `record` | call the provider, write through to the cache |
| `live` | call the provider, neither read nor write the cache |

This is asserted by executing it, not by reading it: the suite runs `replay`, `baseline` and
`eval` with every credential deleted from the environment and the socket constructor rigged
to raise, and separately checks that `httpx` never enters the module table of a replay run.

The cache is committed, so it is the evidence behind every reported number. Determinism is
enforced upstream of it: no wall-clock in a query path, no unseeded randomness, analysis windows
tiled from the fixture span rather than from arrival order, and every prompt-feeding query
ordered explicitly by `(ts_ms, event_id)`.

## 10. Optional — record a fixture from a live stream

Needs `TS_LLM_API_KEY` (an OpenAI key), `DEEPGRAM_API_KEY`, `ffmpeg`, and a channel that is live
right now.
Non-deterministic by nature, and **not** used for any reported result.

```bash
export TS_LLM_API_KEY=... DEEPGRAM_API_KEY=...
make capture CHANNEL=[NAME] MINUTES=10      # no keys — raw bytes only
make enrich  FIXTURE=evals/fixtures/[NAME]  # keys; transcription and frame captions
```

**Export the variables; do not rely on a `.env` file.** Nothing in this codebase calls
`load_dotenv`, so a filled `.env` is read by nobody and enrichment still fails with
"DEEPGRAM_API_KEY is unset". That is deliberate as much as it is unfinished: `.env` here also
sets `TS_LLM_MODE`, and auto-loading it would let a local file silently flip a reviewer's replay
run into live mode. See `RISKS.md` #22.

Capture and enrichment are separate on purpose: capture is time-critical and free, enrichment
runs later from the recorded bytes and is the only step that spends money. Cost per 10-minute
segment: **~$0.056** (measured across 47.6 minutes of audio: $0.205 Deepgram Nova-3 +
$0.060 for 76 `gpt-4.1-mini` frame captions). Running totals are in `COST_LEDGER.md`.

## 11. Before archiving

```bash
make scan
```

Walks the whole tree — dotfiles and `legacy/` included — and exits non-zero on anything that
looks like a credential. It prints `path:line` and the rule that fired, never the matched value.

Two severities. **SECRET IN A PROJECT FILE** means a credential is committed and must be rotated.
**LOCAL-ONLY FILE WITH CREDENTIALS** means `.env` or `.capture_salt` is present, which is normal
on a working machine and fatal in an archive — exclude them explicitly. `.gitignore` does not
protect a directory that is zipped rather than committed.

## 12. Data

`evals/DATA.md` — fixture provenance, permission, pseudonymisation, and the per-case status of
the eleven frozen cases. Gold-label review status per case: `evals/REVIEW_ME.md`.
