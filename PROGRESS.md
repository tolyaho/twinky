# Progress log

Append-only. One block per working session. Never delete history.

Format:

```
## <iso timestamp> — iteration N
Attempted:
Result:
Next:
Blockers:
```

---

## 2026-08-29 — iteration 0
Attempted: scaffold created; determinism spine, cache, provenance validator and eval skeleton
written; unit tests passing offline.
Result: `make test` green. No fixtures yet, no measurements yet.
Next: P0-3 — record 3 fixtures while streams are live.
Blockers: none.

## 2026-08-29T20:24Z — iteration 1
Attempted: A1 — `ingest/enrich.py` Deepgram + vision paths through `ts.cache`, fake-provider tests.
Result: `make test` green, 59 -> 70. New `providers/deepgram.py`, `providers/vision.py`,
`tests/test_enrich.py`. Enrichment now records once and replays byte-identically with the
provider unplugged (asserted). `COST_LEDGER.md` opened at 0.00; no paid calls made.
Next: A2 — wire `ts/cli.py` `replay`, `baseline` and `serve` to the real implementations.
Blockers: none. A1 is code-complete but unexercised on real media — no fixture exists yet (P0-3).

## 2026-08-29T20:47Z — iteration 2
Attempted: A2 — wire `ts/cli.py` `replay`, `baseline` and `serve` to the real implementations.
Result: `make test` green, 70 -> 84. All three commands are real: tiled 60 s windows shared by
both systems, result document per system in `--out`, `CacheMiss` exits 3 without a paid call,
`serve` serves recorded output plus a labelled non-dashboard placeholder (`report/serve.py`).
Fixed a determinism defect found on the way: `trace_id` came from `uuid4`, so two replays of one
fixture produced different published documents. Now derived from `(agent, case_id)`.
Next: RISKS #10 — `python -m ts.cli` fails from a fresh clone without `PYTHONPATH=src`. P0, blocks C2.
Blockers: none for A2. Cache is still empty, so `make replay` exits 3 by design until B1.

## 2026-08-30T00:12Z — iteration 3
Attempted: A3 — wire baseline and agent into `evals/run_eval.py`, verify with fake providers.
Result: `make test` green, 84 -> 94. Both systems run over the identical window per frozen case
and are scored on EVERY emitted card, not just gate survivors — scoring survivors only would
force unsupported-rate to 0 for both and make the headline metric vacuous. Adds
`evidence/predictions.json` (protocol item 4) and an opt-in `--ablation`. `make eval` on an
empty cache exits 3 with no paid call (verified by hand).
Next: A4 — build the remaining 10 eval cases against the sample fixture; cases 5, 11, 12 first.
Blockers: none. RISKS #10 still open (`python -m ts.cli` needs `PYTHONPATH=src`), P0 for gate C2.

## 2026-08-30T00:41Z — iteration 4
Attempted: A4 — build the 12 eval cases against whatever fixtures exist.
Result: `make test` green, 94 -> 98. Built the cases the scaffold fixture honestly supports:
`c03_failure_laughter` and `c12_no_signal_abstain`, taking the frozen set 2 -> 4. Annotated all
four with `fixture_kind`; `make eval` now banners non-capture fixtures NOT A REPORTED RESULT and
prints each fixture's provenance. Case inventory with per-case blockers in `evals/DATA.md`.
Next: A5 — `report/debrief.py`, roll verified cards into the post-stream document.
Blockers: 8 of 12 cases need real captures (RISKS #12, downstream of #2). Case 11 (sarcasm) is
one of the three the product wins on and cannot be written without a real fixture.

## 2026-08-30T01:09Z — iteration 5
Attempted: A5 — `report/debrief.py`, roll verified cards into the post-stream document.
Result: `make test` green, 98 -> 113. `build()` + `render_markdown()` implemented, wired as
`ts.cli debrief` and `make debrief`; writes `<fixture>.debrief.md` and `.json`. Six sections, all
derived from verified cards with no model call. Rendered the artifact by hand and fixed what it
exposed: recurring themes were counting words out of model-written titles and returned "chat",
"says", "the" — now sourced from trigger quotes and answer distributions only.
Next: A6 — dashboard on real replay output; `DESIGN.md` is authoritative.
Blockers: none. RISKS #10 and #12 still open.

## 2026-08-30T01:38Z — iteration 6
Attempted: A6 — dashboard on real replay output, `DESIGN.md` authoritative.
Result: `make test` green, 113 -> 124. Fresh dashboard in `report/static/` (index.html, app.css,
app.js), served by the existing `serve`; the placeholder page is gone. Renders every scored UI
element from `/api/replay` — mode badge, type, share, confidence, trigger quote or explicit
unknown, evidence drawer with message text, gate status, trace id, judge debug panel. Rejected
cards get their own labelled block. `/api/replay` now ships only the events cards cite.
Conformance is tested: every hex must exist in DESIGN.md, display weight <= 300, no shadows, no
network fetch, no `Math.random`, no `innerHTML` assignment. RISKS #4 downgraded; #13 opened.
Next: A7 — `README.md`, `docs/REPRODUCTION.md`, `docs/PRE_EXISTING.md`, numbers as `[TBD]`.
Blockers: none. The editorial marketing sections of DESIGN.md's page sequence (hero, how it
works, measured improvement, changelog) wait on A7 and B-phase numbers — deliberately not built
against `[TBD]`.

## 2026-08-30T02:11Z — iteration 7
Attempted: A7 — `README.md`, `docs/REPRODUCTION.md`, `docs/PRE_EXISTING.md`.
Result: `make test` green, 124 -> 133. Fixed RISKS #10 first, because a truthful reproduction
guide is impossible while every documented command dies with `ModuleNotFoundError`: added
`pyproject.toml` (src layout) and `pip install -e .` to `make setup`; verified `python -m ts.cli`
runs with no `PYTHONPATH` and every target reaches its own exit code. Added a missing `inspect`
target. All three docs rewritten, numbers `[TBD]` where unmeasured. New `tests/test_docs.py`
guards doc/Makefile drift and asserts the documented test count against the real one — it had
already drifted by nine within the same iteration.
Next: B1 — record phase, but it is blocked. No fixture exists (RISKS #2). The next unblocked
work is C1 `make scan` and C4, or fixing RISKS #11 (three declared dependencies nothing imports).
Blockers: A-phase is complete except what needs real captures. B cannot start without P0-3.

## 2026-08-30T02:44Z — iteration 8
Attempted: B is blocked with no fixture (RISKS #2), so took the next unblocked item — C1
`make scan`, no secrets anywhere.
Result: `make test` green, 133 -> 143. The scan was giving false assurance in three separate
ways (RISKS #18): `grep -r .` on macOS never reached `.env`, the pattern list lived in the
Makefile so it matched itself and was permanently red, and `legacy/` was excluded while staying
in the tree. Replaced with `scripts/scan_secrets.py`, 10 tests, two severities, never prints a
matched value. It immediately found two P0s: `legacy/README.original.md:18-23` holds a DB
connection block, a Deepgram key and a Twitch OAuth token (#16), and `.env` holds eight live
credentials while `.gitignore` is inert because this is not a git repository (#17).
Next: C3 — confirm trajectories exist for the agent and both baselines, fill the disclosure
table. C2's fresh-clone run needs a populated cache, so it waits on B.
Blockers: B needs P0-3 fixtures. #16 and #17 need the author: rotate, then exclude from archive.

## 2026-08-30T03:16Z — iteration 9
Attempted: C3 — confirm trajectories exist for the agent and both baselines, fill the
coding-agent disclosure table.
Result: `make test` green, 143 -> 151. Half of C3 was blocked and the other half was worse than
blocked: `trajectories/product-agent/` held 55 files, all test artifacts with case ids like `t3`
that no evaluation case has, and zero real traces. Added `TS_TRACE_DIR`, redirected the suite in
conftest, removed the 55, verified none regenerate. Filled the disclosure table in
`trajectories/coding-agents/README.md` — Claude Code 2.1.246 on Claude Opus 5, the loop method,
and the defects the sessions found; no chat transcript is claimed because none was exported.
`trajectories/README.md` now lists all three systems as owed and `[TBD]`.
Next: C4 — RISKS.md review pass. C2 needs a populated cache and waits on B.
Blockers: #20, no real trajectory for any system, is downstream of #2. B needs P0-3 fixtures.

## 2026-08-30T03:52Z — iteration 10
Attempted: C4 — review pass over `RISKS.md`.
Result: `make test` green, 151 -> 152. Verified claims instead of trusting earlier entries, and
two of them were wrong or incomplete. #11 said three unused dependencies; it is six — the
`deepgram` import hits are this repo's own `ts.providers.deepgram`, not the SDK. New #22:
`load_dotenv` is called nowhere, so a correctly filled `.env` is read by nobody and the record
phase fails with "DEEPGRAM_API_KEY is unset"; `docs/REPRODUCTION.md` §10 told the author to fill
`.env`, which was a false instruction, now corrected and guarded by a test. New #21: the
recorder has never run against a live stream — its own docstring says so — and it is the
critical path tonight. #5 downgraded to partly resolved, #9 superseded by #14/#15, #3 verified by
running with the environment stripped. File reordered by severity with a critical-path header.
Next: B is still blocked on #2. Remaining unblocked work is #11 (drop six unused deps) and the
editorial page sections that wait on measured numbers.
Blockers: #2 gates B, C2, #12, #20 and the video. #16, #17 need the author: rotate, then exclude.

## 2026-08-30T04:19Z — iteration 11
Attempted: RISKS #11 — remove the declared dependencies nothing imports. Every ladder item is
done or blocked on #2, so this was the topmost unblocked work.
Result: `make test` green, 152 -> 154. Dropped `deepgram-sdk`, `fastapi`, `uvicorn`,
`python-dotenv`, `orjson`, `pydantic`, `pytest-asyncio`. Proved rather than asserted: a clean
venv from the reduced file plus `-e .` runs the whole suite green — the packages were still
installed here, so a local pass would have proved nothing. The replay path is now one runtime
package, `httpx`. New test fails the build if a declared package is never imported.
Found on the way (#23): `make setup` cannot run on this machine at all — `python3 -m venv` dies
in `ensurepip` on both Homebrew 3.11 and 3.14. Upstream of anything the project controls, but it
means #10's caveat cannot be closed locally. `docs/REPRODUCTION.md` §2 now documents the `uv`
fallback that was verified to work.
Next: nothing on the ladder is unblocked. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream. #16, #17 need the author to rotate credentials.

## 2026-08-30T04:47Z — iteration 12
Attempted: C2, the half of it that does not need fixtures. The command list is blocked on #2,
but the property C2 exists to prove — no command needs a key or a network — is checkable today.
Result: `make test` green, 154 -> 161. `tests/test_offline_guarantee.py` executes C2's chain
(`replay`, `baseline`, `eval`) with every credential deleted from the environment and
`socket.socket`, `create_connection` and `getaddrinfo` rigged to raise. The chain completes on
cache hits alone; an unrecorded system exits 3 instead of reaching for a provider; a miss reports
a miss and never a missing key. Two out-of-process tests run the CLI with the environment
stripped to PATH and HOME and assert `httpx` never enters the module table. The fake provider is
installed only around the record step, so replay runs against the real provider class — otherwise
the fake, not the socket trap, would be catching the call and the test would prove nothing.
Next: still nothing unblocked on the ladder. #2 gates the rest.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T05:14Z — iteration 13
Attempted: RISKS #21 — de-risk the recorder, the one time-critical step, without a live stream.
Result: `make test` green, 161 -> 169. Everything below the network boundary is now covered, and
covering it found two real defects. A re-run of `capture_media` re-stamped already-timestamped
frames from zero against a new `start_ms`, corrupting every frame timestamp — and capture is the
step that gets retried after it fails. And a capture that produced nothing returned success and
wrote a `meta.json` declaring a good fixture, so the emptiness would have surfaced at enrichment
time with the broadcast over. Both now raise. ffmpeg's return code is checked and its stderr
surfaced; `stamp_frames` is extracted and tested directly; one test drives capture -> enrich ->
`load_fixture` across the real seam. #21 narrowed: a first-contact failure should now mean
streamlink, ffmpeg or the channel, not this module.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T05:41Z — iteration 14
Attempted: `docs/ARCHITECTURE.md` — it feeds Agent Solution & Engineering, the largest single
criterion, and was the last unblocked deliverable I had not read.
Result: `make test` green, 169 -> 186. Checking the diagram against the tree found an overclaim
in two documents at once (#24): the 1m/5m/30m/2h summary hierarchy is listed under "implemented
nodes" in the architecture doc and sits unmarked in the README component table, and no module
implements it — zero matches in `src/`. The README row is mine, written in iteration 7 by
carrying a design table over from `01-PRODUCT.md` without checking it against the code. Both now
mark it as a named gap. The diagram was rewritten with a file against every node and now includes
capture, enrich, the cache and the eval harness, which it previously omitted — exactly the parts
carrying Reproducibility and Measured Improvement. Tests assert every ticked node exists, that
the gap declaration stays in step with the tree, and that the four tool names in the docs are the
four the agent allows.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T06:09Z — iteration 15
Attempted: the last unclosed link of the product invariant — evidence -> streamer action. The
changelog is the other candidate and is genuinely blocked: every competition row needs
`evidence/`.
Result: `make test` green, 186 -> 200. `report/poll.py` turns a verified audience_answer card
into a poll draft, attached server-side to the served payload; the dashboard grew an
"Approve -> draft poll" button that reveals it. Nothing posts: the module holds no client, token
or request and a test enforces that, and the button contains no fetch. Caps are visible, never
silent — a trimmed option is named in the draft's warnings. Fixed one thing while rendering it:
shares were renormalised over the surviving options, so a trimmed poll printed 28% where the card
directly above it said 25%; they now count every vote.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T06:38Z — iteration 16
Attempted: nothing on the ladder is unblocked, so looked for the weakest thing that is. Found a
correctness bug in the provenance gate (#26).
Result: `make test` green, 200 -> 210. A `none` card — the explicit "no signal in this window"
the agent is told to emit — claims nothing, so it cites nothing, so it failed on
`E_NO_EVIDENCE`. Measured before the fix: a correct abstention scored `unsupported_rate = 1.0`,
the headline metric, and rendered in the dashboard's rejected block. Perfect behaviour, worst
possible number, shown to a judge as a failure — and it hit cases 5, 11 and 12 specifically, the
three the product is designed to win on. `none` now takes an abstention path that fails only on
self-contradiction; a passing one is labelled `abstained`; the drawer says there is no claim to
check rather than "0 messages". A test asserts the path did not become a hole in the gate.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T07:05Z — iteration 17
Attempted: continued auditing the gate for places where it fails at its own job. Found #27.
Result: `make test` green, 210 -> 213. `events.window` is half-open and the agent's tools follow
it, but `check_card` accepted an inclusive end. Demonstrated on the sample fixture: a message at
exactly a tile boundary is invisible to window 1's tools and belongs to window 2, yet the gate
verified a window-1 card citing it. Tiles are adjacent, so this was a boundary case on every
window, and it understated the unsupported-card rate — the headline metric — by admitting
evidence the agent provably never saw. Now half-open. Checked that all four frozen gold cards
still pass the gate afterwards, and added a test that keeps that true, so a future tightening
cannot silently invalidate the frozen set.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T07:33Z — iteration 18
Attempted: continued the gate audit — probing for claims that pass without real support.
Result: `make test` green, 213 -> 217. Three holes found by probing. Two fixed (#29): the gate
accepted any event id as evidence, so a card could cite the transcript segment that caused the
signal as the audience's response to it, or offer a frame caption as a message, and be verified
with no violations. Now `E_EVIDENCE_NOT_A_MESSAGE` and `E_CIRCULAR_EVIDENCE`. All four frozen
gold cards still pass, asserted by the guard added last iteration. The third (#28) is left open
on purpose: a one-word quote is trivially verbatim, so `"или"` satisfies the quote check without
proving causation. A minimum quote length would close it, but the frozen metric definition says
"does not appear verbatim", and tightening the rule after publishing the definition would make
the numbers incomparable to the metric they claim to be. Documented in README §11 instead.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T08:02Z — iteration 19
Attempted: moved the audit from the gate to the reducer, the last unaudited named component.
Result: `make test` green, 217 -> 224. Found #30, a product-level defect: `canonical` stripped
`[^\w\s]+`, which removes symbols as well as punctuation, so an emote-only message canonicalised
to nothing and `reduce_chat` dropped it outright. Measured before the fix: 5 messages in, 4 lost,
burst counts summing to 1 — while the module's docstring claims counts and source ids are
preserved. On Twitch an emote flood is the most common reaction there is, so the reducer was
deleting exactly the signal the reaction card exists to catch, and every distribution built on it
under-counted. Punctuation is now stripped by Unicode category so symbols survive, and a
punctuation-only message goes to a counted `∅` bucket. Checked the scaffold fixture reduces
identically — 32 -> 15 bursts, ratio 0.469 — so nothing frozen moved.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T08:31Z — iteration 20
Attempted: audited `evals/scorer.py`, which computes every number the submission reports.
Result: `make test` green, 224 -> 228. Two findings. #31: metric A cannot be lowered by noise —
measured, one correct card plus nine hallucinations reported trigger accuracy 1.0 — and README §6
claimed a denominator of "the cards emitted" that the code never used. Kept the matched-card
denominator, because gold is not exhaustive on twelve cases and scoring every emitted card would
penalise a real signal nobody labelled; corrected the README to describe what is computed and
added `unmatched_rate` beside it in the CSV and the report, where that probe now reads 1.0 / 0.9.
#32: the same gold signal could be matched twice, so a duplicated card weighted one signal twice
in metric A. Matching is now one-to-one in emission order. Nothing has been measured yet, so the
frozen protocol is intact — this was the last moment to change it honestly.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T09:01Z — iteration 21
Attempted: audited the agent controller, the largest scored criterion and the least examined.
Result: `make test` green, 228 -> 233. #33: the "at most 3 cards" cap lived only in the prompt.
Measured — a model returning ten cards had all ten kept, in the agent AND in the baseline, while
`03-EVAL_DESIGN.md` promises the baseline the same output schema and card cap. An unenforced cap
contaminates the comparison: the system that ignores it gets more chances at recall and more
cards over which the unsupported rate is averaged, so the eval would have measured obedience to a
prompt rather than the workflow. `cap_cards` now applies it in one place used by both, unknown
types are filtered first so junk cannot fill the cap, and the dropped count reaches the run
document and the trajectory. #34: tool calls past the fourth were truncated without telling the
model, which cannot distinguish that from a tool returning nothing; the results payload now names
what was not executed.
Next: nothing unblocked remains. #2 gates B, C2, #12, #20 and the video.
Blockers: #2 needs a live stream; #16, #17 need credential rotation by the author.

## 2026-08-30T11:40Z — iteration 22
Attempted: P1 — freeze the eval set against the four real captures; the synthetic-fixture cases
could never produce a reported number.
Result: `make test` green, 233 -> 293. 11 cases built from what the captures actually contain,
including all three the product wins on (5 warning/unknown, 11 sarcasm, 12 abstain). Every id is
resolved from the fixture, never typed; `tests/test_frozen_cases.py` rebuilds a card from each
gold signal and runs the real provenance gate over it — gold that cannot pass the gate scores
every correct card as a silent miss. Cut a 12th case (AURA flood) for sitting 72% inside c05's
window; worst remaining overlap 30%. Labels are model-drafted and unreviewed: `reviewed: false`
everywhere, `evals/REVIEW_ME.md` written for a ten-minute human pass.
Next: P2 — `make baseline CASES=all` first and freeze it before the agent runs.
Blockers: labels need the author (#3 in the author list). Numeric-rating and binary-choice
archetypes do not exist in these captures and were not invented.

## 2026-08-30T12:05Z — iteration 23
Attempted: P2a — diagnose the broken first measurement before changing anything.
Result: two root causes, both single-cause, neither a quality result.
(1) The baseline never emitted a card because it is handed the AGENT's system prompt
(`single_prompt.py:25` imports `SYSTEM` from `workflow.agent`), which specifies a tool-calling
protocol. Verified in the cache: every baseline reply is a well-formed
`{"action":"call_tools",...}` — the model answered correctly, and `.get("cards", [])` then
returned `[]` with no exception raised. A silent zero, the same class as iterations 8 and 13.
Of the 44 calls, 33 are single-turn (11 baseline + 11 ablation + 11 agent step 1) and 11 are the
agent's second step; the counts confirm the baseline did call the model.
(2) 19 of the agent's 20 cards fail on ONE code, `E_CIRCULAR_EVIDENCE`. Every trigger id it
emitted is a chat-message UUID that is also in its own evidence list: it names a chat message as
the cause of the chat it caused. The prompt documents `trigger.event_id` without ever stating
that a trigger must be a speech or screen event and must not appear in evidence — a gap between
the prompt and the gate that scores it, not a modelling failure.
Next: P2b — re-record and re-measure. Changing the prompts invalidates all 44 text cache entries.
Blockers: none. Fix and regression tests land this iteration; the paid re-run is next.
Fix landed same iteration: shared `CARD_CONTRACT` used verbatim by both prompts, baseline given
its own tool-free system prompt, trigger constraint stated, no-`cards` reply recorded as a parse
failure, `make eval` banners and exits 5 on a zero-card system. 13 regression tests;
`make test` 293 -> 306. All 44 text cache entries are now stale by design — the prompts changed,
so P2b must re-record. Nothing in `cache/` was deleted.

## 2026-08-30T12:55Z — iteration 24
Attempted: P2b — re-record and re-measure. Smoke-tested one case first rather than paying for
eleven blind, which found two further plumbing defects before the full run.
Result: all three systems now emit cards and `make eval` reproduces from cache with 48 hits /
0 misses, verified with every credential unset. Measured, 11 cases:
  agent    23 cards | trigger 0.500 | unmatched 0.913 | unsupported 0.739 | recall 0.182
  baseline 20 cards | trigger 0.000 | unmatched 0.950 | unsupported 0.600 | recall 0.091
  ablation 25 cards | trigger 1.000 | unmatched 0.960 | unsupported 0.280 | recall 0.091
The agent doubles the baseline's recall and is the only system to attribute a trigger correctly
at all, and it LOSES the headline metric: 0.739 unsupported against the baseline's 0.600.
Reported, not tuned. The ablation's 1.000 trigger accuracy is 1 matched card out of 25 — which is
exactly why unmatched rate is printed beside it. Two defects found by the smoke test: every
system was citing the `ts` value as the event id because `render_events` led with a bare
bracketed timestamp (fixing it makes the BASELINE stronger), and `DEFAULT_TEXT_MODEL` defaulted
to a model nothing was ever recorded with, so `make eval` reproduced only for someone whose
environment set `TS_TEXT_MODEL` — a broken reproducibility gate for every judge.
Next: P3 — fill the `[TBD]`s from `evidence/`, and diagnose the unsupported-rate loss.
Blockers: none. Cost to date $0.36 of $5.00.

## 2026-08-30T13:20Z — iteration 25
Attempted: P3 — fill every `[TBD]` from `evidence/` and diagnose the agent's unsupported rate.
Result: `make test` green, 309. Every `[TBD]` closed except the video, which genuinely does not
exist. Diagnosis: the agent sets `trigger.event_id` to a chat UUID in 14 of 23 cards, so 8 are
rejected on E_CIRCULAR_EVIDENCE — its single largest failure. The baseline fails oppositely,
9 of 20 on E_TRIGGER_LATE, naming a spoken line that occurs after the messages it caused.
`docs/IMPROVEMENT_CHANGELOG.md` written in full: measured before/after per repair, the discarded
run, the largest contributor (repair 1 — without it there was no baseline and nothing to
measure), three removed experiments with their results, the failure mode with a case id, and the
hot take. Corrected stale claims found while filling: trajectories/README said "empty" with 33
real runs on disk, ARCHITECTURE said "4 of 12 cases", README said fixtures are ten minutes, and
§6 asserted labels were "reviewed by the author" while every gold file says `reviewed: false`.
Next: P4 dashboard editorial sections, or P5 gate. P5 is worth more.
Blockers: none. Cost unchanged at $0.36 of $5.00 — this iteration spent nothing.

## 2026-08-30T14:10Z — iteration 26
Attempted: P5 — the qualification gate, run as an actual fresh clone rather than read.
Result: `make test` green, 319 -> 334. Four gate defects found by executing it, all P0 for
Reproducibility, which is scored before anything else.
(1) `make setup` failed from a clean clone: `streamlink==8.0.0` needs Python 3.10+ while macOS
ships 3.9 as `python3`, so pip died with a resolver error before `make test` could run — on a
package no graded command imports. Split into `requirements-record.txt`; `make setup` now
installs the graded path only and checks the interpreter, failing in a second with an actionable
message instead of a wall of pip output.
(2) `make replay` and `make baseline` over a whole fixture exited 3: the cache held the 11 frozen
case windows, not the 60 s tiles those commands generate. Recorded both for yugi and
stableronaldo ($0.03); the documented commands now run from cache.
(3) Recording crashed mid-run: a model answering `{"cards": ["text"]}` hit `str.get` in
`cap_cards`. The baseline already handled that; the agent did not, so paid calls for every
earlier window were lost. Now filtered, with tests.
(4) `make debrief` crashed on `"distribution": "single mention"` — a string where a mapping was
assumed. Model output is untrusted in shape, not just content.
`make scan` is clean for the first time: RISKS #35 fixed, so placeholders like
`DB_PASSWORD=your_password` no longer outrank the real credentials in `.env`. `SUBMISSION.md`
written. Verified end to end from /tmp: setup, test, eval, inspect, baseline, replay, debrief,
all with every credential unset and 0 API calls.
Next: P5 remainder — RISKS.md review pass and build/open the archive. Then P6 video assets.
Blockers: none. Cost $0.39 of $5.00.

## 2026-08-30T14:35Z — iteration 27
Attempted: P5 remainder — RISKS.md review pass, archive built and opened, disclosure checked.
Result: `make test` green, 334. Reviewed by executing claims, not re-reading them. Closed #2
(four fixtures), #12 (eleven frozen cases), #20 (33 trajectories), #21 (recorder run four times:
47.6 min audio, 3863 messages, 72 frames), #5 (vision model called 76 times, defaulted to the
recorded model), #35 (scanner placeholders). Rewrote the critical-path header, which still said
no fixture existed. Opened #36 gold labels unconfirmed, #37 repo private so judges cannot access
it, #38 the agent losing the headline metric, #39 the agent abstaining without checking frames,
#40 and #41 for the gate defects fixed last iteration. Two stale duplicates removed.
Archive: `make archive` added so packaging is reproducible rather than ad hoc — it zips HEAD
(never the working tree, which holds `.env` and raw media), unzips it and scans the result.
Verified by opening it: 524 files, 1.9 MB, no `.env`, no salt, no raw media, scan clean, and
from the extracted zip `make test` 334 passed and `make eval` reproduced at 37 hits / 0 misses.
Next: P6 — video shot list and a clean `make demo` walkthrough. P4 dashboard editorial after.
Blockers: none. Cost unchanged at $0.39 of $5.00 — this iteration spent nothing.

## 2026-08-30T15:00Z — iteration 28
Attempted: P6 — video support assets and a clean `make demo` walkthrough.
Result: `make test` green, 334. `video/SHOTLIST.md` written: 17 shots in capture order, exact
commands, what each proves, and the lines to say out loud — including the ones that count
against us. Verified `make demo` end to end: 13 windows, 5 verified, 19 rejected, 37 events,
0 server errors, every command in the list executed before being written down.
Three findings while filming-by-proxy. (1) The storyboard's "approve -> draft poll" beat cannot
be filmed: no card in any recorded run carries a `distribution`, so `build_draft` correctly
returns None. The last link of the invariant is code-complete and unexercised — RISKS #42, and
the shot list says cut it rather than stage it. (2) `make eval` did not reproduce the committed
`report.md`: it omitted `--ablation`, so running it on camera would have silently rewritten the
three-row table the README quotes with a two-row one. Now included; replay is free. (3) That
change surfaced a real shift: iteration 27's `cap_cards` repair means a reply like
`{"cards": ["text", {...}]}` keeps the valid card instead of discarding everything, so the
baseline went 20 -> 21 cards and unsupported 0.600 -> 0.619. Propagated to every table and
declared as Repair 5 in the changelog rather than quietly re-run — it narrows the gap against us.
Next: P4 dashboard editorial sections, the last unstarted ladder item.
Blockers: none. Cost unchanged at $0.39 of $5.00.

## 2026-08-30T15:35Z — iteration 29
Attempted: P4 — the dashboard editorial sections that needed measured numbers.
Result: `make test` green, 334 -> 339. Hero, measured-improvement and changelog sections added
to `report/static/`, rendered live and verified: all three system rows populate, 0 server errors.
The numbers are READ, never recomputed in the browser: `make eval` now also writes
`evidence/summary.json`, the machine-readable twin of the printed table, and `serve.payload`
carries it through as `evaluation`. `evals/scorer.py` stays the single owner of every published
metric — a rate derived a second time in JavaScript would eventually disagree with the one in
`report.md`, and a test now forbids deriving any of the four published rates client-side.
Without an eval the section stays hidden rather than rendering zeros that read like a measured
result. No colour was improvised: every hex in `app.css` is still a DESIGN.md token, display
weight stays 300, hairlines not shadows, 96px section rhythm.
The editorial copy states the result that counts against the product — "wins grounding, loses
restraint", the worst unsupported rate of the three, and the ablation's accuracy resting on a
single matched card — and a test asserts those sentences stay there, so the page cannot be
quietly reworded into a win.
Next: the ladder is complete. Everything remaining is author-only: video, gold review, repo
visibility, credential rotation, submission.
Blockers: none. Cost unchanged at $0.39 of $5.00.

## 2026-08-30T15:55Z — iteration 30
Attempted: nothing on the ladder is unfinished — P1 through P6 are all done — so took the
topmost remaining risk instead: the results table is hand-propagated across five documents and
has already been rewritten twice, once when the measurement landed and once when a repair moved
the baseline from 20 cards to 21.
Result: `make test` green, 339 -> 351. `tests/test_published_numbers.py` parses every results
table in README, SUBMISSION, the changelog, the shot list and `evidence/report.md`, and asserts
each row against `evidence/summary.json` — the machine-readable twin written by the same
`aggregate()` that prints the table. Also checks every `$X total` claim against the ledger's
running total. Verified by mutating a published number and watching it fail with the exact
document, row and field named, then restoring it.
The vacuity guards paid for themselves immediately: they caught that my own regex was silently
matching only two of the three systems, because the ablation row carries a `¹` footnote marker
that broke the value cell. A consistency check that quietly stops checking is the same failure
class as the Makefile `grep` scan and the pre-rewrite secret scan, both of which gave false
assurance in this project already. Every document now also has to keep all three rows.
Next: nothing. The ladder is complete and the remaining work is author-only.
Blockers: none. Cost unchanged at $0.39 of $5.00.

## 2026-08-30T16:05Z — iteration 31
Attempted: block A (gate items) of the frontend/farm ladder, with the fixture farm started first
per block D.
Result: `make test` green, 351 -> 354. Farm running in the background, capture-only, verified it
references no enrich path and no API key before starting it. `legacy/frontend/` REMOVED from the
tree rather than merely excluded from packaging: it is a dashboard shell driven entirely by
generated data — `chat-simulator.js`, `messageGenerator`, `Math.random` across six files
including its `index.html` — and an export-ignore would have hidden it from the zip while leaving
it in a public repository, which is the half-fix. 27 files gone, the other 32 legacy files kept
and still disclosed. `.env` packaging closed off three ways and asserted by test: untracked,
`git archive HEAD` cannot include an untracked file by construction, and `.gitattributes` marks
it export-ignore anyway. `make scan` clean; archive verified by opening it.
Caught while verifying: the archive still contained `legacy/frontend/` because `git archive`
reads HEAD and the deletion was only staged. The check found it, which is the point of opening
the archive rather than trusting the target.
Next: block B — the shared-spec re-measure. It is paid and changes all three systems identically.
Blockers: none. Cost unchanged at $0.39 of $5.00.

## 2026-08-30T16:25Z — iteration 32
Attempted: block B — the shared-spec re-measure, whose premise is that the shared prompt never
states a trigger must be a speech or frame event.
Result: `make test` green, 354. The premise is false and the change was not made. That sentence
is already in `CARD_CONTRACT`, added as Repair 2 in iteration 23, and in stronger terms than the
brief proposes — it forbids a chat id explicitly and forbids reusing an evidence id as the
trigger. Checked in the cache rather than the source: 129 of 173 recorded text requests carry the
rule, and the 44 that do not are the discarded first run, so every request behind the published
table was sent with it.
Examined all eight surviving E_CIRCULAR_EVIDENCE cards: every one names a chat UUID that is also
in its own evidence list, which two clauses forbid, and three set `kind: "unknown"` beside a
concrete id, contradicting the same paragraph. Not ambiguity being exploited — stated rules not
being followed by gpt-4.1-nano.
Rejected two follow-ups as tuning: rewording the rule again, and enforcing it in the controller
the way `cap_cards` enforces the card cap. The second is defensible in principle and still wrong
here — the agent names a chat trigger 14 times to the baseline's once, so a symmetric guard is
asymmetric in effect, and it was chosen after seeing the score. Published as a proposed-and-not-
made iteration in the changelog with the evidence; #38 narrowed from "contract defect" to "model
behaviour".
Next: block C, the frontend, time-boxed 3 hours.
Blockers: none. Cost unchanged at $0.39 of $5.00 — this block spent nothing.

## 2026-08-30T16:50Z — iteration 33
Attempted: block C, first item — pull the ElevenLabs reference, reconcile it with DESIGN.md, then
the two cheapest wins it names: type and space.
Result: `make test` green, 354 -> 359. `npx getdesign` could not run — no Node toolchain on this
machine at all — so the template came from the published npm tarball directly
(`getdesign@0.6.25`, `templates/elevenlabs.md`), which is the same artifact the CLI would install.
Reconciliation is a verified no-op: all 19 colour tokens match in BOTH directions, and the display
and Inter scales are identical row for row. DESIGN.md needed no correction and its provenance is
now recorded at the top of the file.
The gap was that the CSS did not use the scale it documents. The hero rendered at the 48px
display-xl row instead of the 64px/300/1.05/-1.92px display-mega row — most of why the page read
as a tool rather than an editorial surface. Fixed, with a mobile step down. Two uppercase labels I
added last iteration had improvised .8px tracking and no weight, so they did not match the badges
already on the page; both now use the caption-uppercase row, 12px/600/1.4/+0.96px. Stat row moved
to the 12-column grid. Five tests pin the hero row, the uppercase scale, the +0.16px body
tracking, display weight <= 300 and the colour rule, so the type cannot drift back.
Block C item 5 was already done: deleting `legacy/frontend/` in block A took the Spline blob,
glass-liquid and gradient bars with it — zero matches left in `report/static/`.
Next: block C item 3, the hero driven by real replay data, then item 4, drawer motion.
Blockers: none. Cost unchanged at $0.39 of $5.00 — this block spent nothing.

## 2026-08-30T17:40Z — iteration 34
Attempted: the frontend visual pass — reference reconciliation, then type, space, atmosphere,
the hero stage, card and drawer treatment, and the editorial results table.
Result: `make test` green, 359 -> 366. The dashboard is now the LIGHT editorial system the
reference and DESIGN.md both describe — off-white canvas, white cards at radius 16 with a 1px
hairline, ink type — instead of the dark developer-tools canvas it had been, which DESIGN.md
never asked for. Two soft orbs as atmosphere: fixed, blurred 110px, opacity .38, z-index -1,
pointer-events none, drifting on a 46/58s alternate; a test pins them inside the atmosphere range
and forbids an orb colour appearing anywhere but the orbs.
Signal status is now monochrome. `verified` / `abstained` / `rejected` are carried by label,
weight and hairline, never by colour — a product decision, not a style one: a colour-coded status
invites skimming instead of opening the evidence, which is the one thing the product asks for.
`--success` and `--error` no longer appear in the stylesheet.
The hero stage plays REAL replay data: the messages a verified card actually cites, accelerating,
freezing on the shortest one — on stableronaldo that is "mitosis", meaningless alone — then
collapsing into the cards the system actually produced, with the trigger line beneath. No
randomness, index-derived timing, a stop control and a Replay button, so it can be filmed
without jitter. If a run verified nothing there is no argument to make and the stage stays
hidden rather than animating a claim the system never produced.
Tightened rather than weakened one test: it forbade `box-shadow` outright, which was stricter
than DESIGN.md, whose `--shadow-hover` is documented as "the ONLY shadow tier" on hovered cards.
It now requires the value to be that token, the token to match DESIGN.md, and every use to sit on
a `:hover` selector — and a second test asserts only one tier is ever defined.
Caught while verifying: a stale server was holding port 8000, so my first check of
`make demo FIXTURE=yugi` was actually reading the previous stableronaldo instance. Re-ran clean.
Next: the box has an hour or so left. The video is not started and is the hard deliverable.
Blockers: none. Cost unchanged at $0.39 of $5.00 — this pass spent nothing.

## 2026-08-30T18:20Z — iteration 35
Attempted: frontend polish pass — spacing, navbar, glassmorphism, story, using the ui-ux-pro-max
skill for guidance rather than taste.
Result: `make test` green, 366 -> 371. Ran the skill's `--design-system` query first and
DISCARDED its output: it returned an "Enterprise Gateway" pattern with a #1E40AF/#D97706 blue and
amber palette and Fira Code, which contradicts the locked ElevenLabs system on three enforced
rules at once — saturated accent, display weight, warm neutrals. The skill's own contract says to
verify fit before applying, so its palette and typography were not used. Its accessibility
guidance and the glassmorphism spec were kept, and both were on target.
Real gap it found: **zero focus styles in the entire stylesheet**, which the guidance rates HIGH
severity. Added `:focus-visible` with a 2px ink ring and offset, `cursor: pointer` on every
operable control, and a test that fails if an outline is ever removed without replacement.
Glass done properly rather than sprinkled: `--glass-bg/-border/-blur` added to DESIGN.md FIRST
with the reasoning, translucent white so it carries no hue and the palette is unchanged, blur
16px inside the 10-20px band the spec gives, `-webkit-` prefix for Safari, and a test that
restricts it to the two surfaces that overlap scrolling content — the sticky bar and the stage
header. Fixed a real bug while there: the bar was measured rather than full-bleed, so its glass
stopped short of the viewport edge and left a visible seam on wide screens.
Spacing was the main complaint and the main fix: page padding 48 -> 96, hero bottom 48 -> 96,
card padding 24 -> 32, rail gap 20 -> 24, drawer 16 -> 24, lede margin 32 -> 48.
Story: four numbered eyebrows now carry the argument — what the audience said, what did not
survive, whether it is actually better, how it got here — with a test pinning the order.
Blockers: none. Cost unchanged at $0.39 of $5.00.

## 2026-08-30T19:45Z — iteration 36
Attempted: the UI pass, worked in the numbered order after the author actually looked at the page.
Result: `make test` green, 371 -> 386. Eight items, each committed separately.
(1) The hero showed the wrong data and disproved its own headline: three cards reading "Chat
mention of X" under "caused by unknown unknown". It is now pinned server-side to the window where
the argument is provable and shows ONE grounded card. Searched every recorded run for cards that
are gate-clean, non-abstaining, naming a real event with a verbatim quote — 14 exist. The best is
on the sleep-stream word game: chat types li-words and lands on "libral" while the frame shows
"librarian" correctly guessed, with ZERO transcript segments in the window. The stream is built
backwards from the cited message so it arrives at the freeze; taking the first N left the payoff
off the end. The card came from the single-prompt BASELINE, not the agent, so the stage says so —
presenting it unlabelled under the product's headline would have been the quiet misrepresentation.
(2) Three rendering bugs fixed: the literal "unknown unknown" is now one sentence, the `CAUSE`
label had no margin ("CAUSENot established."), and a distribution with one bucket drew a column
of indices with a vertical one-character label — charts now need two distinct non-zero buckets or
the fact is printed as text.
(3) Section 01 was headed "Verified audience signals" over cards badged ABSTAINED. Renamed to
"Signals with a cause" and abstentions given their own block framed as correct behaviour.
(4) Wordmark: a filled dot bound by a hairline to an outlined dot — signal bound to its cause —
in the nav and as the favicon; SVG content type added to the server.
(5-6) Inter stack with the full scale applied, mono only for ids and timestamps, hero split into
claim (cols 1-7) and proof (8-12) so the dead right half is gone, cards 2-up above 1100px, stat
numbers at 48/300.
(8) Cards as objects: the quote is now the emphasis at 18px italic with a hairline rule, the type
badge is quiet with no fill, the drawer caret rotates and the evidence rows stagger in.
Blockers: none. Cost unchanged at $0.39 of $5.00 — this pass spent nothing.

## 2026-08-30T20:10Z — iteration 37
Attempted: UI pass 2 — information architecture, in the numbered order.
Result: `make test` green, 386 -> 393.
Item 1's premise did not hold, and checking it was worth the $0.02. The brief says default to
yugi or marlon because stableronaldo produces no grounded cards. Measured across every recorded
run: **the agent grounds nothing on any fixture** — stableronaldo 0, yugi 0, and marlon 0 after
recording its tiles specifically to test the hypothesis. yugi is in fact WORSE than stableronaldo
for the agent: 0 verified of any kind against 5. Only the baseline grounds anything (6 / 2 / 1).
So no default fixture fixes the empty section; it is RISKS #38/#39 surfacing in the UI.
That turned the picker into the answer rather than a nice-to-have: it switches **system** as well
as fixture, so the empty agent state becomes the comparison the product is actually about instead
of an apology. `/api/fixtures` lists enriched fixtures with recorded runs; `/api/replay` takes
`fixture` and `system`. A fixture name off a query string is passed through `Path(...).name` and
must resolve beside the served fixture — verified by requesting `../../../etc`, which falls back.
Three sections collapsed into one with a segmented control and counts in the labels — they were
always one thing, every card the run produced, in three outcomes. Cards 2-up, six visible, show
all beneath. Empty states are one line with no reserved height, which is what produced the 300px
voids. Hero proof card rebuilt as one object at full card width with the title on one line and
the footnote inside the padding. Navbar gained section anchors with an IntersectionObserver
underline, a hairline that appears only after scroll, and `scroll-margin-top` so headings do not
hide behind it. "How it works" built — four steps, one line each.
Blockers: none. Cost $0.41 of $5.00.

## 2026-08-30T21:15Z — iteration 38
Attempted: Phase 1 of the product page — time-accurate replay as the front page, evidence moved
to /method. Phase 2 (true live) NOT started: it needs keys and money and is explicitly gated
behind Phase 1 shipping.
Result: `make test` green, 393 -> 403. `/api/stream` is Server-Sent Events over committed files
only — chat emitted at `ts_ms - origin`, cards at the moment their window CLOSED, because that is
the first instant the agent could have produced them; emitting at window start would show the
answer before the evidence. No model call, no key, no cost, asserted by a test that greps the
function body for a provider.
Two things had to be got right or the page would lie. The server had to become
`ThreadingHTTPServer`: an SSE connection is held open for the whole playback, and on the
single-threaded server the page itself would never load while a stream ran — verified by
requesting `/` and `/method` mid-stream. And the opening frame could not be named `open`, because
EventSource reserves that for its own connection event, so a custom listener never fires and the
badge would silently keep its placeholder text. Renamed to `meta`; the badge now echoes the
server's own `mode` and `speed`, so a replay running at 8x cannot display 1x.
Front page: two columns, chat on `canvas-soft` left, signals on `canvas` right, one hairline
between, no boxes. Cards rise and fade in, and when one lands the messages it cites light up in
the flood beside it — that gesture is the whole thesis. Counters at 48/300, play/pause, restart,
1x/4x/8x. DOM capped at 200 rows, counter uncapped.
Verified: full playback to `done` (1535 chat + 24 cards at 8x), routes all 200, page loads during
a stream, and with an empty `evidence/` the chat still plays with zero cards rather than failing.
Blockers: none. Cost unchanged at $0.41 — this pass spent nothing.

## 2026-08-30T22:00Z — iteration 39
Attempted: bound the chat window, from screenshots the author took — the first time anyone has
actually looked at this page.
Result: `make test` green, 403 -> 406.
The chat column grew without limit, so the counter row — the one line saying what the flood
turned into — was pushed off the bottom of the screen. The shell is now exactly `100vh` with
`overflow: hidden`, and only the two columns scroll. The load-bearing detail is `min-height: 0`
on the grid and on each column: without it a flex/grid child refuses to shrink below its content
and the page scrolls instead of the panes. The ticker is `flex: none` so the counters cannot be
scrolled away. Chips and the disclosure line now share one compact strip instead of stacking into
a ~300px void above the columns.
Diagnosed rather than assumed: the screenshot showed 158 messages with all three card counters at
zero, which looks broken. It is not — the first card lands at 56.5s after 163 messages, so the
capture was five messages early. But a blank panel for the first minute reads as broken to anyone
watching, so the server now sends `first_card_ms` and the column states "analysis windows are 60
seconds, the first closes at 0:56" with a progress bar. A run that produced no cards at all says
that instead of waiting forever.
Third time the colour guard tripped on its own documentation — a comment naming the `#000` it
forbids. Made it read declarations only, the way the `unknown unknown` and `Math.random` guards
already do. A check that fires on prose gets deleted rather than fixed.
Blockers: none. Cost unchanged at $0.41 — this pass spent nothing.

## 2026-08-30T22:35Z — iteration 40
Attempted: chat layout, boxes and lining, from a third screenshot.
Result: `make test` green, 406 -> 409.
One real bug: the waiting message was rendering at the BOTTOM of the signals column. It was a
sibling of `.signals`, which is `flex: 1`, so the flex container took all the space and pushed the
message to the floor — furthest from where a reader is looking while waiting. Moved inside the
column, and `reset()` now recreates it there rather than relying on markup it had just cleared.
Visual: the chat column read as a grey BOX with hard corners, which re-introduced the container
the two-column layout exists to remove. The tint is now a bleed layer (`inset: 0 0 0 -100vw`,
`z-index: -1`) so it has no visible edge — a field with one hairline beside it, which is what the
brief asked for. The strip above the columns stacked chips and disclosure onto two lines and left
a gap; it is one 40px row now, with the note truncating rather than wrapping and hiding below
1100px. The macOS overlay scrollbar was a dark slab sitting on the text — both panes now use a
6px thumb on a transparent track in `hairline-strong`, darkening on hover. Chat rows: author ids
right-aligned against the text column so every message starts on one hard left edge, mono dropped
to 12px, row padding up to 5px for a readable rhythm at speed.
Two guards needed anchoring after the CSS moved: both split on a selector string that a newly
added shared rule also matched. Same class as the comment-matching guards — a check that binds to
text rather than structure drifts silently.
Blockers: none. Cost unchanged at $0.41 — this pass spent nothing.

## 2026-08-30T23:10Z — iteration 41
Attempted: the product page reads as a dashboard rather than an editorial page — author feedback
on a fourth screenshot: hard to parse, components not distinguishable, lines not clear.
Result: `make test` green, 409 -> 411. The tension was real and worth naming: DESIGN.md is an
editorial marketing system — airy, hairline-only, generous whitespace — and this page is an
operator surface where a streamer scans for signal at a glance. Tokens are unchanged and every
hex still comes from DESIGN.md; what changed is density and structure.
Panels: each pane is now a bounded `surface-card` panel with a `hairline-strong` border, a radius
and its own header strip on `canvas-soft` carrying the title, a mono count chip and a one-line
purpose ("raw, unfiltered" / "cause proven, evidence attached"). The page sits on
`surface-strong`, so the panels read as objects on a deck.
Lines given a hierarchy: `hairline-strong` for anything structural — panel borders, header rules,
the bar — and the lighter tiers only inside a panel. Previously everything was one weight, which
is why nothing separated.
The flood became a table: zebra rows on `canvas-soft`, per-row bottom rules, hover, a 3px left
rule reserved for the citation highlight, ids right-aligned. Counters became four bordered KPI
tiles with `grounded` outlined in ink as the one that matters. Controls grouped into their own
bordered cluster. The floating chips row became a labelled toolbar, which also removed the
~60px dead band above the columns.
Reversed one test deliberately: it asserted the chat column must be "a field, not a box" on the
reading that a box re-introduces a widget. Shown the result, that was wrong for this surface, and
the test now asserts the opposite with the reasoning recorded rather than silently deleted.
Blockers: none. Cost unchanged at $0.41.

## 2026-08-30T23:45Z — iteration 42
Attempted: read the grounding situation, fix what is legitimately fixable, and the UI with it.
Result: `make test` green, 411 -> 414.
The grounding finding, restated: the agent names a cause its evidence supports on ZERO cards
across all three fixtures. Structurally it can only cite ids it has actually seen, and when it
answers after `group_repeated` alone the only ids in its context are chat ids — which the gate
correctly rejects. The fix is a tool-selection change, which is #39, which is explicitly out of
scope and would be tuning after publication. Not done, for the eleventh time, and the reason is
recorded rather than re-argued.
What WAS broken and is now fixed is the UI telling of it. The signals panel header read
"Grounded signals · 0" above five visible cards, because the count showed `grounded` while the
panel renders grounded AND abstained. Exactly the failure already fixed once on the method page —
a heading claiming what its contents deny. The header is now "Signals", the count is what the
panel shows, and a sub-line spells out "N grounded · M abstained".
A run that grounds nothing now says so once, in place: "no card in this run names a cause its
evidence supports — that is the measured result for this system, not a loading state", with one
click to the baseline on the same window, which grounds 2. Printing the finding beats an empty
panel that reads as broken.
Card states are now tellable apart without colour: a solid ink left rule for grounded, a light
one for abstained. Weight and line, never hue — the same rule the badges follow.
Fourth guard to match its own comment. Stripping comments before checking is now the house
pattern for every text-based assertion in this suite.
Blockers: none. Cost unchanged at $0.41.

## 2026-08-31T00:05Z — iteration 43
Attempted: the stacking stat rows on /method, from a screenshot.
Result: `make test` green, 414 -> 416. Two bugs, one visible and one not.
Visible: `renderHero` and `renderScores` appended into containers they never emptied, so every
fixture or system switch stacked another copy of the four stat tiles and another set of table
rows under the previous ones — the screenshot shows six stacked copies. `renderDebug` had it too
and had simply not been noticed. All three now go through one `clear()` helper.
Not visible, and worse: the mode badge read **RECORD**. It was rendering `result.mode`, which is
the mode the run was CAPTURED in — the baseline and marlon documents literally say `"record"` —
so a page that only ever serves committed files was telling a viewer it was recording. The badge
now says how the page is serving it, REPLAY, and the captured mode moved into the debug panel as
provenance beside a new "served: replay from the committed cache" row. Confirmed the values that
caused it: 2 of 3 run documents carry `mode=record`.
Blockers: none. Cost unchanged at $0.41.

## 2026-08-31T00:45Z — iteration 44
Attempted: live mode (Phase 2) and the philosophy page.
Result: `make test` green, 416 -> 433. Cost $0.41 -> $0.42.
**Live works end to end against a real broadcast.** stableronaldo was live; one 60-second window
captured, enriched and analysed: 113 chat messages, 3 cards, 104.8 s wall clock, ~$0.006. My
first liveness probe said every channel was offline and was wrong — the shell loop used `timeout`,
which does not exist on macOS, so the whole probe silently reported nothing live. Worth noting
because it nearly stopped this being built at all.
Two real bugs found by running it rather than reasoning about it. The cache defaulted to REPLAY
mode, and live audio has by definition never been seen, so the first window died on a cache miss.
Fixed to record — into a temporary cache of its own, which matters more: `cache/llm/` IS the
artifact a judge replays, and filling it with entries keyed on bytes that can never recur would
grow it with entries no replay will ever hit. Verified the committed cache is byte-unchanged
across a live run, 289 entries before and after.
The second was caught by an existing guard: the live session wrote a trace straight into
`trajectories/`, the graded deliverable — the same pollution that once put 55 test artifacts
there. Traces now go to a temp directory. The guard from iteration 9 earned its keep.
Guards: refuses to start past a $3.00 live cap (the project cap is $5.00), stops itself after ten
minutes, reports spend per window against the ledger, sanitises the channel name before it
reaches a subprocess, and treats an offline channel as a message rather than an error. Replay
remains the default and nothing goes live on page load. 14 tests, all deterministic.
`/philosophy` written: the thesis, the uncomfortable ablation result stated in full, the
discipline of not tuning, and four open failures listed rather than implied — including that the
agent grounds nothing. A test asserts those numbers and admissions stay on the page.
Blockers: none. Cost $0.42 of $5.00.

## 2026-08-31T01:15Z — iteration 45
Attempted: fix and finish — re-run the qualification gate now that live, SSE, threading and two
new routes exist, and bring the submission documents up to date with them.
Result: `make test` green, 433, and the gate passes from a freshly built archive.
The gate found a real defect, which is why it is run rather than assumed. Two tests added in the
packaging pass call `git ls-files`, which raises outside a repository — so a judge who unzips the
archive and runs `make test` got two failures on a tree that is otherwise perfect. They now ask
what would reach a judge and answer it correctly in both contexts: the tracked set in a checkout,
the files on disk in an unpacked archive. The archive form is the stronger check.
Also ruled out a reproducibility regression before it could bite: `ts.live` imports `capture`,
and `streamlink`/`websockets` are deliberately absent from the graded requirements. They are
imported lazily inside functions, so `ts.live` loads without them — verified in a venv built from
`requirements.txt` alone.
Verified from the extracted zip with a stripped environment: 433 tests green, `make eval`
reproduces at 48 hits / 0 misses, and all five routes plus the SSE stream serve correctly with
`mode: replay`. `make scan` reports zero project-file findings. No stale test count or cost
figure remains in any document.
Docs updated for what now exists: SUBMISSION.md lists the three routes and the live demo path
with its guards and its one measured session; README describes them; RISKS #43 opened for live
being exercised once rather than hardened, with what is and is not covered stated explicitly.
Blockers: none. Cost $0.42 of $5.00.

## 2026-08-31T01:35Z — iteration 46
Attempted: finish the gate properly by opening the archive and using it as a judge would.
Result: found the worst defect of the session and fixed it. `make test` 433 green in the archive,
`make eval` reproduces at 48 hits / 0 misses, and all three fixtures replay at 0 misses.
**The product page was non-functional in the archive.** `evidence/raw-results/` was gitignored in
the packaging pass, described there as "regenerable noise". It is not noise: the picker lists a
fixture only when a run document exists for it, and the stream reads cards from the same files.
In the archive the picker offered ZERO channels and the stream carried ZERO cards — a judge
unzipping it and running `make demo` would have watched chat scroll into an empty panel forever.
Nothing failed, nothing errored; it simply showed nothing, which is why the earlier route checks
all returned 200 and looked fine.
Two things made it invisible until now. The checks were run against the working tree, where the
files exist. And "regenerable" was true in the narrow sense — `make replay` rebuilds them from
cache at zero cost — but nothing tells a judge to run it, and a demo that requires three
undocumented commands before it shows anything is a broken demo. 164 KB was the whole cost.
Also committed 46 cache entries from the marlon recording that had never been staged, without
which that fixture exits 3 on replay.
The gate keeps earning its place: this iteration it caught a dead product page, and the previous
one caught two tests that fail outside a git checkout. Both were invisible from inside the repo.
Blockers: none. Cost $0.42 of $5.00.

## 2026-08-31T01:55Z — iteration 47
Attempted: item A, P0 bugs 1.1-1.5 plus the regression test 1.2 asks for. 1.6 is the long one and
gets its own iteration.
Result: `make test` green, 433 -> 443.
**1.2 does not reproduce and I did not invent a fix for it.** Twelve abrupt mid-stream socket
resets (SO_LINGER 0, so RST not FIN) across two fixtures, plus six overlapping streams abandoned
in the same second: server healthy, `/api/fixtures` 200, zero errors in stderr. The most likely
reason is the switch to `ThreadingHTTPServer` two iterations ago, made to stop an SSE connection
blocking page loads — on the single-threaded server a write to a dead socket takes out
`serve_forever`'s only thread, which is exactly "the make demo process was gone". Pinned as a
regression test anyway: open the stream, reset the connection after the first bytes, assert
`/api/fixtures` still answers. The property was restored by accident; it is now held on purpose.
1.1: the error handler was `() => source.close()` and said nothing, so a refused stream left the
page on "Connecting to the recording…" with the previous run's badge above it. There is now a
named failure state with a retry, the badge reads NO STREAM, and controls come back. `reset()`
clears badge and channel line too, so a failed `start()` cannot leave the last run's identity on
screen.
1.2 client half, done independently of the crash: every `start()` takes an epoch and all four
listeners ignore stale events — including `done`, which otherwise lets an abandoned stream
disable the live one's controls. Picker chips and speed buttons are debounced at 120 ms.
1.3: `main > section { margin-top: 96px }` was reaching the dashboard panels. One line.
1.4: a 133-character sentence in a 46ch nowrap clamp, measured 750px against 348px. Sentence
replaced, clamp untouched, the rest belongs on the Method page.
1.5: three pages now share one nav — Live · Method · Why — asserted by a test that compares the
hrefs across all three rather than checking each in isolation.
Next: 1.6, the citation highlight firing off-screen. Then item B.
Blockers: none. Cost unchanged at $0.42.

## 2026-08-31T02:10Z — iteration 48
Attempted: P0 1.6 — the citation highlight firing off-screen. Item A is now complete.
Result: `make test` green, 443 -> 447.
The feed pinned to the bottom on every message, while a card is emitted at its window's END and
cites messages from the window's start — up to 60 seconds and roughly 100 rows above. So the
highlight always fired somewhere nobody could see, and it is the single gesture the whole product
rests on: this cluster, that cause.
The feed now yields to it. When a card lands, following stops, the first cited row scrolls to
centre, the highlight holds 1.8 s, and after a 1.5 s hold the feed resumes — unless another
citation arrived or the reader took over, tracked by a hold token so two citations in quick
succession do not fight. Scrolling up is treated as a deliberate act: following stops and a
"↓ follow live" pill appears until clicked, with 40px of the bottom counted as still following.
A cited row that has already been evicted past the 200-row DOM cap is skipped rather than
throwing, and a card whose rows are all gone leaves the feed alone.
FEATURES_V2.md added to the loop with its own priority order: after the board, the free
deterministic set — questions panel, chatter stats, masonry — then group labels, then D and E.
Embeddings only if the board is green and the video is scheduled, and only with hand-labelled
pair-level precision and recall frozen before any arm runs. The team measured embedding
clustering twice and got ~100 poor clusters; it goes in as a measured arm or not at all.
Next: item B, the deterministic grouping rules.
Blockers: none. Cost unchanged at $0.42.

## Iteration 49 — 2026-08-31 — item B, the deterministic grouping rules

Attempted: DASHBOARD.md §0 — grouping arm B in `workflow/reduce.py`, so the board stops drawing
one card per chat message.

The defect, in the module's own terms: `reduce_chat` groups by exact canonical equality, and its
docstring promises to collapse duplicates and retain counts. On a word-guessing stream twenty
people type twenty different strings, so exact matching splits one audience signal into twenty
rows of one and the method page renders "Audience mentions 'dracula'" over and over, each with
`Evidence — 1 message`, each rejected `E_CIRCULAR_EVIDENCE`. One message is not evidence of an
audience reaction.

Added `group_chat`, `Group`, `is_reaction` and `grouped_summary` **beside** `reduce_chat`, which
is byte-identical. That is deliberate: `reduce_chat`'s output goes into the agent's prompt and is
hashed into every recorded model call, so rewriting it would miss the cache on all eleven frozen
cases and take keyless replay with it. Three rules, in order — reaction wave (laughter and
emote-only, one counted bucket), rule B (single-word messages ≥4 chars, first 4 characters,
groups ≥4), rule A (content token, stopwords and tokens <3 chars dropped, ≥3 messages). Each
message joins one group only; candidate counts are read once before anything is placed, so
placement order cannot change the result.

Two defects found by measuring rather than by reading:

- **marlon w6 drew `violet` twice** — 19 as a token group from the sentences, 8 as a `viol…`
  prefix group from the single words. One signal, two rows: the bug being fixed. A prefix bucket
  now folds into the word it prefixes, and the row reads **`violet × 27`**, which is the figure
  DASHBOARD.md predicted, reproduced exactly.
- **`jump` collided with itself** — reachable both as a 4-character prefix and as a content
  token, sharing one dict key, so whichever rule ran second relabelled the other's group. Keys
  are now namespaced by rule.

Measured on the committed fixtures, no keys, no cost:

| window | exact-match groups | grouped rows | top row |
|---|---:|---:|---|
| stableronaldo w9 | 76 | 7 | **`para… × 41`** — parade, parallel, parat |
| stableronaldo w3 | 60 | 4 | `drac… × 55` — dracula, draconic, draculas |
| stableronaldo w2 | 61 | 5 | `amet… × 21` — amethyst, amethyist, amethysts |
| marlon w0 | 134 | 12 | `aura… × 38` — AURA, Aura, AURAAAAAAAAAAAAA |
| marlon (0715) w6 | — | — | **`violet × 27`** — VIOLET MYERS, is that violet |

The frame caption for stableronaldo w9 reads *"a word-guessing game is active… the partial word
`para_`"*, and the top row is now 41 people brute-forcing it. That row is the thesis in one line
of UI, on a stream with zero audio, computed with no model.

`DASHBOARD.md` predicted `para… × 38` and `rang… × 21`; the shipped rules measure **41** and
**20**. The plan's figures were estimated against a slightly different rule set — the reaction
bucket is pulled first here, and prefixes fold into tokens — so the measured numbers are the ones
published. Only `violet × 27` matched the plan exactly.

No compression figure was published anywhere, so nothing had to be retracted: the only mentions
are `compression_ratio` as a field name in `docs/REPRODUCTION.md` and `video/SHOTLIST.md`. The
grouped-vs-exact figures above are per-window and stated as such.

Result: `make test` 447 → **461 passed**. Fourteen new tests, including both measured figures
pinned to their fixtures and a guard asserting `reduce_chat` still returns 76 groups on
stableronaldo w9 with counts summing to the window. Six rows in DECISIONS.md.

Not done: nothing in the UI reads `group_chat` yet — that is item C, the board and rail.
Next: item C.
Blockers: none. Cost unchanged at $0.42.

## Iteration 50 — 2026-08-31 — item C part one, the board and rail computed

Attempted: DASHBOARD.md §1 and WHAT_WE_SHOW.md — turn a window into rows and real statistics.
New module `report/board.py`: `board()`, `rail()`, `questions()`, `is_question()`, `windows()`.
Deterministic, free, no key, no model — which is also Tier 0 of live mode, so it has to hold up
where no paid provider is reachable at all.

**A row is a trigger → the groups that followed it, with counts and verbatim messages.** The
first attempt used nearest-preceding speech or frame caption and it produced something false:
on stableronaldo w9 it attached `para… × 41` — forty-one people brute-forcing an on-screen word
puzzle — to a caption reading *"three people sleeping in a dimly lit room"*. A row header reads
as causal however it is captioned, so attribution is now two-tier and the tier is on the row:

- **`matched`** — the trigger text contains the word chat is typing. stableronaldo w0: the
  caption names the guessed word `ranger` and the top group is `rang… × 20`.
- **`preceding`** — only the last thing said or shown before the wave started. Adjacency.

Measured across all 15 recorded fixtures: **104 rows over 36 windows — 16 matched, 88 preceding,
12 unattributed groups.** Matched rows sort first. Neither tier goes through the provenance gate,
because neither claims causation; the gate ledger sits in the same rail counting the agent's
cards separately, so the two are never mistaken for each other.

marlon w6 reproduces the WHAT_WE_SHOW.md example on real data: speech *"Hey, man. They're coming
for you, bro… What the fuck is going on?"* → **`violet × 27`**, samples *"violet murders?"*,
*"VIOLET MYERS"*, *"VIOLET."* — the streamer is mid-sentence asking what is going on and the room
answered a minute ago. Footer: **237 messages · 4 rows · 123 singletons**. The doc predicted 4
rows and 179 singletons; rows match, singletons do not, because arm B groups more than the
estimate did. The measured figure is the published one.

The rail: rate sparkline in 10s buckets, peak burst and per-second velocity, unique chatters,
new chatters against who spoke before, messages per chatter, concentration (top 10% share),
composition `N → M → K`, reaction-wave count, questions, speech segments with an explicit
`silent` flag, frame captions, and the gate ledger by code.

Questions needed two corrections, both found by measuring. Anchoring the question word at
position zero lost "whats the game" and "yo what game"; allowing an auxiliary in second position
turned *"Capri is 19"* and *"There is a whole P star right there"* into questions. Final rule:
wh-word in either of the first two tokens, auxiliary only in the first, and a content token
required either way. On marlon 0715 w6 the bare `ends with ?` rule returns **29** hits, at least
6 of them literally `?`-only; the filter returns 22 rows over 31 asked. FEATURES_V2 quoted 54 for
"one marlon window" without saying which — 29 is what this window measures, so 29 is published.

Result: `make test` 461 → **479 passed**. 18 new tests in `tests/test_board.py`, including both
attribution tiers, the unattributed path, the flagship marlon row, the silent-window truth on
stableronaldo, and the gate ledger. Six rows in DECISIONS.md.

Not done: nothing renders this yet. `serve.py` does not call `board()` and the page still has two
columns. Cost unchanged at $0.42.
Next: item C part two — wire `board()`/`rail()` into `/api/stream` and build the three-zone
layout.
Blockers: none.

## Iteration 51 — 2026-08-31 — item C part two, the dashboard is three zones

Attempted: wire `board()`/`rail()` into the server and rebuild the page around them.

`stream_events` now emits a `board` event per 60s tile, carrying that window's rows and rail, at
the moment the tile closes — the same instant its cards arrive, because that is the earliest the
window can be described at all. `new_chatters` accumulates across tiles, so it means new rather
than "everyone, every window". Added `/api/board?fixture=&window=n` for reading one window
without waiting for the stream to reach it.

The page is three zones: the flood on the left, what it means in the middle, the numbers behind
both on the right. The middle column holds two different kinds of thing and shows **one at a
time**, behind a `Board | Signals` control — a deterministic row and a gated card drawn in the
same column read as the same kind of claim, and they are not. A row states the strength of its
link in words (`names it` / `just before`) and in line weight, never in colour, since the palette
has no state colours. Clicking a row highlights every message behind it in the feed, reusing the
citation gesture, so a count of 27 is checkable rather than asserted.

The rail: rate sparkline, volume and peak velocity, who is talking (unique, new, per-chatter,
top-10% share), composition, questions, stream context with `silent window` stated rather than
left blank, and the gate ledger by code.

Verified against a running server rather than deduced. `/api/board` on marlon w6 returns
`237 messages · 4 rows · 123 singletons`, top row speech → `violet × 27`, top question
*"violet murders?"* asked 8 times. A 22-second SSE read of stableronaldo at 8× carried 361 chat,
2 card and **2 board** events; the first board is `163 messages · 2 rows · 75 singletons` with
the **matched** row (`rang…`, against a caption naming the guessed word) sorted above a larger
`preceding` one. `/`, `/method`, `/philosophy`, `/api/fixtures` all 200; window 999 returns 404.

Five existing dashboard guards failed on the new layout and were **rewritten, not deleted**: two
panels became three, `>Signals<` moved into a tab, `highlightCited` split into `highlightIds`,
the empty-state selector, and two new uppercase labels that had improvised tracking — those were
brought onto the `.96px` scale rather than the assertion being loosened. No new hex entered
`app.css`; all sixteen are still the DESIGN.md set.

Result: `make test` 479 → **490 passed**. 11 new tests, six rows in DECISIONS.md.

Not done: masonry (§6), the questions panel as a section rather than a rail block (§3), and the
`REPLAY | LIVE` segmented control. Cost unchanged at $0.42.
Next: the FEATURES_V2 ship-today set — questions panel, chatter stats surfaced properly, masonry.
Blockers: none.

## Iteration 52 — 2026-08-31 — the questions panel

Attempted: FEATURES_V2 §3 — the one feature on the page a chat-only system provably cannot build.

Added `answered_by()` and `stream_questions()` to `report/board.py`, a `Questions` tab beside
`Board` and `Signals`, and a cumulative question payload on every board event. Whether a question
was answered is decided by reading the **transcript after it was asked** — which is the whole
point: a chat-only system has the question and no way to know whether it was ever picked up.

The first rule matched on a single shared content word and it was mostly wrong. Measured on
marlon: 10 answers, of which nine were coincidence — *"whos fucking dad"* answered by *"the
fucking water is this shit"*, *"WHYS SHE HERE"* by a line containing "here", *"Who is Marlon
Yall"* by a line containing "coke". Two shared words is now the threshold.

That costs a real match: *"ETA?"* → *"ETA 10:36."* shares one token and is now marked unanswered.
Accepted deliberately. Telling a streamer they answered something they did not takes it off the
list they came here for; leaving an answered question on the list only adds noise to it.

Measured after the fix, on the committed fixtures:

| fixture | questions | asked | answered |
|---|---:|---:|---:|
| yugi | 38 | 45 | **2** |
| marlon 0715 | 72 | 105 | **0** |
| stableronaldo | 16 | 16 | **0** — zero transcript segments, so nothing could be answered |

Both yugi answers are the streamer picking the question up out loud, and the first is the whole
argument in one row: **"Yugi how do u feel abt Redify switching u for…" asked 6 times → *"how do
you feel that Reddify switching you for XQC?"*** matched on `feel`, `switching`, `xqc`. marlon's
head of the unanswered list is `violet murders?` asked **14** times and never picked up.

The panel shows the line the streamer actually said, with its timestamp, rather than only a
verdict — the link is lexical, the same family as a `matched` board row, and a verdict with no
evidence under it is what this project refuses everywhere else. Unanswered sorts first. Clicking
a row highlights every message that asked it.

Verified against a running server: an 8× SSE read of yugi carried the cumulative question payload
on each board event, with `why violet myers at the party` → *"my god. I remember that Violet Myers
party."* via `myers`, `party`, `violet`.

One existing guard was rewritten rather than loosened: the two-way middle-column toggle became a
three-entry `VIEWS` table, so the test now asserts every pane is hidden unless active.

Result: `make test` 490 → **498 passed**. 8 new tests, five rows in DECISIONS.md. No new hex in
`app.css` — still the sixteen from DESIGN.md. Cost unchanged at $0.42.
Next: chatter stats surfaced properly (§4) and the masonry board (§6).
Blockers: none.

## Iteration 53 — 2026-08-31 — WINDOWS.md, the board counts live

Attempted: WINDOWS.md — the board sat blank for a full minute before anything appeared, which
reads as broken rather than pending.

The premise checked out and I verified the load-bearing half myself: **all 11 frozen cases carry
exactly 60000 ms `window_ms` spans.** So shrinking the analysis window would change the prompt
bounds, kill every cached response, turn replay into all misses, and invalidate the cases and
gold labels — the entire comparison, a day out. The analysis window stays at 60 s.

What moved is the **grouping refresh**, which was never the same thing. Grouping calls no model,
so it can run constantly: `rolling_groups()` recounts over a trailing 60 s every 2 s and the
stream carries a `tick`. A group is drawn the moment it crosses the threshold and its count ticks
up as chat arrives — measured on marlon: `reaction wave 7 → 15 → 16`, `slam 6 → 8`.

Measured time to the first row on screen, against the first window close:

| fixture | first live row | first board | before |
|---|---:|---:|---:|
| marlon 0715 | **2.0 s** | 60.0 s | 60.0 s |
| stableronaldo | **10.0 s** | 56.5 s | 56.5 s |
| yugi | **44.0 s** | 59.3 s | 59.3 s |

Computed on the server, not ported to JavaScript: grouping is one rule set with tests pinned to
measured numbers, a second implementation in the browser would drift, and there is no JS runtime
here to test one with. Cost measured at **0.4 ms per recount, 0.19 s to build a whole fixture's
script** — free, as predicted.

Two things fixed by measuring. The first payload was **966 KB of ticks per fixture, more than the
chat it was describing**; trimming to 12 ids and 2 samples and dropping ticks identical to their
predecessor took stableronaldo from 359 ticks to 258 and 966 KB to 485 KB. And a tick carries no
`trigger` field at all — rather than trusting the UI not to draw a cause on a live count, the
payload has none to draw. The block is dashed, headed *"this minute so far"*, and says *"counting
· no cause assigned yet"*, with a one-pixel hairline showing time to the next close.

A side effect worth noting: the sliding window sees waves the tiles split. `drac…` is 55 in tile
w3 and **74** across the boundary at 250 s.

WINDOWS.md's own table comparing 30 s / 20 s / 10 s windows is a measurement I did not take, so
it is recorded as post-deadline work rather than repeated as mine.

Result: `make test` 498 → **506 passed**. 8 new tests, five rows in DECISIONS.md. No new hex —
still the sixteen from DESIGN.md. Cost unchanged at $0.42.
Next: chatter stats surfaced properly (§4) and the masonry board (§6).
Blockers: none.

## Iteration 54 — 2026-08-31 — FEATURES_V2 §4 checked, §6 masonry shipped

Attempted: the last two of the ship-today set.

**§4, chatter statistics — already done.** Checked against the spec rather than rebuilt: unique
chatters, new chatters relative to who spoke before, messages per chatter, top-10% concentration,
the 10s rate sparkline, peak burst and its velocity all landed in the rail in iteration 50.
Measured on marlon w6 to confirm: 140 unique, 140 new, 1.69 per chatter, 0.291 concentration,
peak 75 per 10s = 7.5/s, rate `[8, 26, 29, 40, 75, 59]`. Nothing in §4 is missing, and the
things it explicitly rules out — emote leaderboards, top-chatter rankings, sentiment lines, word
clouds — are still absent.

**§6, masonry and the entry animation — shipped.** Rows now flow in two columns above 1500px
with `break-inside: avoid`, and stay in one column below it. That breakpoint is the decision: in
the 600px board two tracks would be 290px each, narrower than the quote line each row carries,
so masonry there costs legibility and buys nothing. Rank survives because CSS columns fill
top-to-bottom — the strongest row is still the first thing under the heading.

`.boardrows` moved from a flex column with `gap` to block flow with margins, because `gap` does
not survive the switch to columns and the rows would have collided the moment the viewport
crossed the breakpoint.

Rows arrive with the same short translate-and-fade the signal cards already use — one motion
vocabulary, not two. That introduced a real failure mode and a guard for it: rows start at
`opacity: 0`, so a node appended without its class is an invisible node. `test_every_row_drawn_is
_a_row_made_visible` asserts the orphan block is made visible in the same pass as the attributed
rows, and the reduced-motion block now restores the resting state rather than only zeroing the
duration — the existing global rule kills transitions, which would have left an unclassed row
invisible rather than still.

Verified on a running server: the served stylesheet carries all four rules and `/` returns 200.

Result: `make test` 506 → **511 passed**. 5 new tests, six rows in DECISIONS.md. No new hex —
still the sixteen from DESIGN.md. Cost unchanged at $0.42.

The FEATURES_V2 ship-today set is complete: grouping arm B, questions panel, chatter stats,
masonry.
Next: FIX_GROUNDING_AND_UI.md §1–2 — putting the window's transcript segments and frame captions
into the model's turn with their ids — which the plan rates above D and E now that A–C have
landed.
Blockers: none.

## Iteration 55 — 2026-08-31 — FIX_GROUNDING_AND_UI §1, the diagnosis

Attempted: §1, which is explicitly read-only — answer one capability question from `agent.py`
and a cached request body, write the answer down, stop. No code changed.

**The question:** when the model is asked to name a trigger, does the prompt put the window's
non-chat candidates — transcript segments and frame captions, with their event ids — in front of
it, or does it only state the rule and leave the model to fetch them?

**The answer is NO.** The agent's entire opening user turn is two sentences, verbatim from
`cache/llm/04/041a143d…json`:

```
Analyse the window start_ms=1788075308171 end_ms=1788075309123.
Call tools to see what happened, then answer.
```

Zero event ids. Across all **57** recorded openings the agent wrote for itself, **not one
contains an event id of any kind.** (79 two-message agent-prompt openings exist in the cache;
the other 11 carry rendered events and are leftovers from the discarded first run, where the
baseline was handed the agent's tool-calling prompt — a bug already logged and fixed.)

Meanwhile `CARD_CONTRACT` requires exactly what the prompt withholds: *"`trigger.event_id` … is
a SPEECH id or a SCREEN id. It is NEVER a chat id"* and *"Every id you cite must be one you
actually saw in the input."*

So the model must fetch the candidates itself. Measured over the 70 cached agent conversations
that carry TOOL RESULTS — counting only the controller's result turns, not the tool names in the
system prompt:

| tool | conversations where its results appear |
|---|---:|
| `group_repeated` (chat) | **70 / 70 — 100%** |
| `get_transcript_window` | 10 / 70 — 14% |
| `get_frame_captions` | **2 / 70 — 3%** |
| `get_chat_window` | 2 / 70 — 3% |

The agent sees chat in every single conversation and the screen in three percent of them, and is
then required to name a screen or speech id it "actually saw". In 97% of conversations the only
ids it has ever been shown are chat ids, so citing chat is the only move available to it.

**That makes `E_CIRCULAR_EVIDENCE` a missing input, not a disobedient model** — the quantitative
form of logged failure #39, and it settles the open question §1 was asked to settle. It also
means the refusal in iteration 32 was right for the reason given then and is untouched by this:
the contract does state the rule, the controller still does not enforce it, and nothing about
scoring has moved.

Cost this iteration: $0.00. Ledger unchanged at $0.42 (169 cache entries, 289 files).
Next: §2 — supply the candidates in the turn. Note for that iteration: §2 prescribes re-recording
the agent, which changes every cache key and therefore the published agent numbers. That is
legitimate per §2 and must be written up as its own iteration with before/after, baseline and
ablation left frozen, and reverted if the delta is not an improvement.
Blockers: none. `make test` untouched at 511 passed.

## Iteration 56 — 2026-08-31 — FIX_GROUNDING_AND_UI §2, the grounded arm, built and unrecorded

Attempted: §2 — put the window's speech and screen events into the model's turn with their ids.

Built as **a second arm, `agent_grounded`, not as a re-recorded `agent`.** §2 prescribes
re-recording the agent; that changes every cache key, and the committed cache is how a judge
reproduces every published number with no API key. A second arm measures the same question and
leaves the published comparison standing whichever way it goes — an improvement with both arms on
the record, or a removed experiment with a result.

`stream_context()` renders the window's transcript segments and frame captions as
`id=… ts=… | text`, capped at 12 and 6 and clipped to 240 characters, and the grounded opening
names that list as the only source of trigger ids while keeping `unknown` explicitly available.
Blank segments are dropped — Deepgram emits them, and an id over a blank line spends a slot
saying nothing. `inline_context=False` everywhere by default; `run_eval.py` gains `--grounded`
and the Makefile does not pass it.

What the model would now see on stableronaldo w0 — the window where it emitted *"No clear speech
or on-screen content detected"*:

```
SCREEN in this window (frame captions):
  id=frm_e51ae0df39 ts=1788074587878 | … A word-guessing game is active on screen with the
                                        prompt "r a _ _ _ _ _". …
  id=frm_bfd997f846 ts=1788074617878 | … the word "ranger" correctly guessed by a user name…
```

**Nothing published moved, and that was verified rather than assumed.** `make replay` 29 hits /
0 misses, `make baseline` 13/0, `make eval` **48 hits / 0 misses**, and `evidence/report.md`,
`comparison.csv` and `summary.json` are byte-identical. The only diff in a raw result is
`mode: record → replay` with the cards unchanged. A new test pins the default opening turn to a
real committed cache entry, because that one string is what the reproduction claim rests on and
nothing else in the suite would have caught an edit to it.

**Found while verifying: `make replay` typed with no arguments was exiting 3 on committed state.**
`FIXTURE` defaulted to `evals/fixtures/sample`, the scaffold, which has no recording — while
README.md line 172 promises `make test`, `make baseline`, `make replay` and `make eval` all run
with no keys. Pre-existing, confirmed by stashing this iteration's changes and reproducing it.
The default is now a recorded fixture and both bare commands work from cache.

Result: `make test` 511 → **521 passed**. 10 new tests in `tests/test_grounded_arm.py`, six rows
in DECISIONS.md. Cost this iteration: **$0.00**, ledger unchanged at $0.42.

**Not done and stated plainly: the arm is unmeasured.** No recording exists for it, so there is
no number for it on the frozen set and none may be published until there is.
Next: the paid record phase — one fixture first to measure real cost, then the eleven cases if it
is affordable. Check COST_LEDGER.md, log the run, leave baseline and ablation frozen.
Blockers: none.
