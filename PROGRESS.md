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
