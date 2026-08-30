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
