# Evaluation data

## Fixtures

| Fixture | Source | Duration | Permission | Notes |
|---|---|---|---|---|
| `self_*` | Own stream, recorded by the author | ~10 min | Owned | Scripted ground truth: N questions asked aloud, M deliberately left unanswered |
| <!-- TODO --> | | | | |

## Pseudonymisation

Chatter usernames are replaced by a stable salted hash before anything is committed. The salt is
not committed. Broadcaster login is retained since it is public and identifies the source.

## What is committed

`meta.json`, `chat.jsonl` (pseudonymised), `frames/` captions, `transcript.jsonl`.
Raw audio is **not** committed (see `.gitignore`).

## Rights

Only self-recorded or explicitly permitted material. Public chat text is retained solely as
evaluation input, pseudonymised, and is not redistributed as a dataset.

## Case inventory

Case numbers follow the matrix in `../../notes/03-EVAL_DESIGN.md`. `fixture_kind` in each case
file declares where its numbers come from; only `capture` is reportable, and `make eval` puts a
"NOT A REPORTED RESULT" banner at the top of `report.md` for anything else.

| # | Case | Status | Blocked on |
|---|---|---|---|
| 1 | Binary choice asked aloud | `c01_binary_choice` | — |
| 2 | Numeric rating, bare numbers in chat | **not built** | P0-3: no fixture contains a rating question |
| 3 | Gameplay failure triggers laughter | `c03_failure_laughter` | — |
| 4 | Name mention triggers a meme flood | **not built** | P0-3 |
| 5 | Warning with no cause in speech → `unknown` | `c05_warning_no_cause` | — |
| 6 | Teammate speech misattributed (diarization) | **not built** | P0-3 — needs real diarized audio; cannot be hand-written |
| 7 | Frame matters while speech is silent | **not built** | P0-3 |
| 8 | Speech matters while the frame is uninformative | **not built** | P0-3 |
| 9 | Two competing topics at once | **not built** | P0-3 |
| 10 | Heavy spam collapses without losing volume | **not built** | P0-3 — the scaffold's laughter wave is the same window as case 3 |
| 11 | Sarcasm → confidence must drop | **not built** | P0-3 |
| 12 | No signal → abstain | `c12_no_signal_abstain` | — |
| 13 | Prompt injection inside chat, treated as data | **not built** | optional; P0-3 |
| 14 | Reference depending on an earlier window | **not built** | optional; P0-3 |

4 of 12 built. All four run against `sample`, the hand-written scaffold fixture, so **none of
them can produce a reported number** — they prove the evaluation runs end to end. Of the three
cases the product is designed to win on (5, 11, 12), two are built and case 11 (sarcasm) needs a
real capture.

The eight remaining cases are not written blind. Writing a gold label for sarcasm, diarization
failure or competing topics against a fixture authored to contain exactly those phenomena would
be grading the system against a script it was handed.
