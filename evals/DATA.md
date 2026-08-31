# Evaluation data

## Fixtures

| Fixture | Source | Duration | Chat | Speech | Frames | Notes |
|---|---|---|---|---|---|---|
| `stableronaldo_2026-08-30T0723` | Public Twitch broadcast | 720 s | 1288 | **0 seg** | 24 | Sleep stream at 03:23 local with an automated word-guessing overlay. No speech — see below |
| `yugi_2026-08-30T0723` | Public Twitch broadcast | 720 s | 625 | 138 seg | 24 | IRL/podcast, two diarized speakers in a vehicle |
| `marlon_2026-08-30T0715` | Public Twitch broadcast | 600 s | 1535 | 97 seg | 20 | IRL party stream, heavy chat, copypasta campaigns |
| `marlon_2026-08-30T0701` | Public Twitch broadcast | 120 s | 415 | 3 seg | 4 | Short capture, game footage, chat complaining about audio |
| `sample` | Hand-written | 24 s | 32 | 3 | 2 | Synthetic scaffold so the repo runs on first clone. **Never a reported result** |

## Pseudonymisation

Chatter usernames are replaced by a stable salted hash before anything is committed. The salt is
not committed. Broadcaster login is retained since it is public and identifies the source.

## What is committed

`meta.json`, `chat.jsonl` (author field pseudonymised — see the limit below), `frames/`
captions, `transcript.jsonl`. Raw audio is **not** committed (see `.gitignore`).

### What "pseudonymised" covers, exactly

`pseudonym()` in `src/ts/ingest/capture.py` replaces the **author** of every message with a
salted one-way hash, and the salt is not distributed. It does not touch message **text**.

Chat text contains `@mentions`, and those are real handles. Measured across the four evaluated
fixtures: **172 mentions naming 88 distinct handles**, none of them pseudonyms.

| fixture | @-mentions in message text |
|---|---:|
| `yugi_2026-08-30T0723` | 86 |
| `marlon_2026-08-30T0715` | 59 |
| `stableronaldo_2026-08-30T0723` | 26 |
| `marlon_2026-08-30T0701` | 1 |

**This is stated rather than fixed, and the reason is structural.** Event ids are derived from
message content, so rewriting the text would change every id, which changes every prompt, which
changes every cache key — and keyless reproduction, the property the whole submission rests on,
would stop working. The fixtures are frozen for exactly this reason. Scrubbing them now would
trade a documented limitation for a broken evaluation.

So the honest claim is the narrow one: **authorship is pseudonymised; the public chat text is
retained verbatim, mentions included**, as evaluation input and not as a redistributable dataset.
`RISKS.md` #53 carries it, and `video/SHOTLIST.md` already tells the author not to dwell on the
raw feed on camera for a related reason.

## Rights

Only self-recorded or explicitly permitted material. Public chat text is retained solely as
evaluation input, pseudonymised, and is not redistributed as a dataset.

## Case inventory

Case numbers follow the matrix in `../../notes/03-EVAL_DESIGN.md`. `fixture_kind` in each case
file declares where its numbers come from; only `capture` is reportable, and `make eval` puts a
"NOT A REPORTED RESULT" banner at the top of `report.md` for anything else.

**Eleven cases, all against real captures.** Frozen 2026-08-30, before any measurement run.

| Case | Fixture | Type | Trigger | Tests |
|---|---|---|---|---|
| `c01_word_puzzle_amethyst` | stableronaldo | audience_answer | frame | Answer distribution grounded in an on-screen prompt, zero speech |
| `c02_word_puzzle_herald` | stableronaldo | audience_answer | frame | Distribution reflects the spread, not only the winner |
| `c03_failure_laughter` | marlon_0715 | reaction | speech | Laughter attributed to the spoken line that caused it |
| `c05_warning_no_cause` | marlon_0701 | warning | **unknown** | Warning found in noise, with no provable cause |
| `c06_two_speakers_laughter` | yugi | reaction | speech | Trigger attribution across two diarized speakers |
| `c07_frame_only_dracorex` | stableronaldo | audience_answer | frame | Chat provably uninterpretable without the frame |
| `c08_pool_jump_reaction` | marlon_0701 | reaction | frame | Frame cause while speech discusses something else |
| `c09_two_topics` | marlon_0715 | reaction ×2 | **unknown** | Two concurrent signals separated, not merged |
| `c10_spam_collapse` | marlon_0715 | reaction | **unknown** | Reducer collapses near-identical repeats, counts preserved |
| `c11_sarcasm_mockery` | marlon_0715 | reaction | **unknown** | Derision read as derision, not as praise |
| `c12_no_signal_abstain` | yugi | *(abstain)* | — | No audience signal → `none`, not a manufactured card |

All three cases the product is designed to win on — 5 (warning, no cause), 11 (sarcasm),
12 (abstain) — are built against real captures.

Across 12 gold signals: 4 frame triggers, 2 speech triggers, 5 `unknown`, 1 abstention. Four
fixtures. Two cases have no speech at all in the window. Worst window overlap between any two
cases is 30%; a twelfth case was cut for sitting 72% inside `c05`.

### Gold-label provenance

**Gold labels were drafted with model assistance from the captured fixtures and reviewed by the
author. Draft status per case is tracked in `evals/REVIEW_ME.md`.** Every gold file carries a
`"reviewed"` flag; anything still `false` at submission is declared in README §6 rather than
hidden. No label claims human authorship a human has not given.

Every `trigger_event_id` and `relevant_message_id` is resolved from the fixture itself rather
than typed by hand, and `tests/test_frozen_cases.py` rebuilds a card from each gold signal and
runs it through the real provenance gate — a gold label that could not itself pass the gate
would silently score every correct card as a miss.

### Archetypes deliberately absent

Cases were built from what the captures contain, not from a wish list:

- **Numeric rating** — zero bare-number replies in any of the four fixtures. These are IRL and
  podcast streams, not gaming streams where "rate this out of ten" occurs.
- **Binary choice** — the one real candidate lands 8 s before its fixture ends, leaving no room
  for chat to answer inside a 60 s window.
- **Prompt injection** — no chat message in any fixture attempts it.

Writing a fixture to contain a phenomenon and then grading against it would be grading the
system against a script it was handed.

### stableronaldo_2026-08-30T0723 — no speech
Captured audio measures -57.4 dB mean. Transcription returned zero segments. A +28 dB gain
experiment brought the mean to -28.9 dB and still returned zero segments, confirming the window
contains no speech rather than inaudible speech. The original audio is retained unmodified.
This fixture is therefore used for cases that must succeed without speech: frame-grounded
reactions, spam collapse, competing topics, and abstention.

## Why `evals/fixtures/` holds 27 directories and the documents say four

Four fixtures are enriched and evaluable. They are the four in the table above, and they are the
only ones any reported number comes from. The rest are there because capture is time-critical and
enrichment is not: a broadcast has to be recorded while it is live, and the transcription and
frame captions can be produced from those bytes at any time afterwards — for a price.

| | count | what is committed |
|---|---:|---|
| **enriched, evaluated** | 4 | `chat.jsonl`, `transcript.jsonl`, `frames.jsonl`, `meta.json` |
| captured, never enriched | 22 | `meta.json` only — **11 KB in total** |
| synthetic scaffold (`sample`) | 1 | hand-written, 36 events, used by tests and by nothing else |

The 22 are **8 channels, 32,958 chat messages, 2.9 hours** of broadcast, held as a record of what
was recorded rather than as data. Their `raw/` directories are gitignored, so no audio, no video
and no unpseudonymised login is committed for any of them, and the derived event files were never
produced. `make inspect` on one succeeds and reports **0 events** — it is empty, not broken.

They are kept rather than deleted for one reason: `meta.json` records that the capture happened,
when, on which channel and how much chat it held. Deleting them would erase the only evidence of
how the four were chosen, which was from a wider set and not from the first thing that worked.
Enriching all of them was a cost decision, not an oversight — see `COST_LEDGER.md`, where the four
cost **$0.28** and the same treatment for twenty-six would have dominated the entire budget.
