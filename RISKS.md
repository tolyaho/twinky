# Risks to the qualification gate

Reviewed 2026-08-30 03:50 MSK. Numbers are stable across revisions — `PROGRESS.md` refers to
them — so rows are reordered by severity, never renumbered.

## The critical path, and what it costs

Everything unscored traces back to one thing: **no fixture has been recorded** (#2). Downstream
of it sit the eight missing eval cases (#12, blocks Measured Improvement, 15 pts), all three
required trajectories (#20), the whole B phase, and the C2 fresh-clone run. The video (#6) also
needs footage that only a real fixture produces.

The recorder itself has never been run against a live stream (#21). That is the sharp edge: if
capture fails on first contact there is no fallback, and it fails at the moment there is least
time to fix it.

Decision gate is Sunday 20:00 MSK; submission is Monday 21:00 MSK (18:00 UTC).

Before any of that, rotate the credentials in #17 and #1. They are live, and were already exposed
once. (#16 claimed a third copy in `legacy/`; it was a scanner false positive — see the fixed
table and #35.)

---

## P0 — do these first

| # | Risk | Status | What to do |
|---|---|---|---|
| 17 | `.env` holds eight live credentials | **OPEN** | Twitch, Deepgram, Anthropic, OpenAI, DeepSeek and DB credentials. Now genuinely ignored: the tree became a git repository 2026-08-30 and `.env` is covered by `.gitignore`, verified with `git check-ignore`. The ignore rule does not protect a **zip**, so still exclude it explicitly at packaging time. `make scan` reports it as a shipping blocker. |
| 1 | Credentials pasted in the team Telegram group (Twitch secret, MySQL creds, Anthropic key) | **OPEN** | Rotate regardless of the hackathon. Never commit the export. Still live — see #16, #17. |
| 2 | No fixtures recorded; P0-3 needs streams live | **OPEN — the critical path** | 3 × ~10 min. Self-stream one as a guaranteed fallback. Everything below marked "downstream of #2" unblocks the moment this lands. |
| 21 | The fixture recorder has never been run against a live stream | **OPEN — narrowed 2026-08-30** | The network boundary is still unexercised: no Twitch egress here. Everything below it now is — frame stamping, retry safety, the ffmpeg failure path, the empty-capture guard, and the capture → enrich → `load_fixture` seam, 8 tests. Two real defects were fixed in the process: a re-run stamped already-timestamped frames from zero against a new start time, and a capture that produced nothing returned success and wrote a `meta.json` declaring a good fixture. Still run it once on a 60-second segment and check `make inspect` before committing to three full captures. |
| 22 | `.env` is never read — `python-dotenv` is declared but `load_dotenv` is called nowhere | **OPEN — new 2026-08-30** | Verified: zero call sites in `src/`, `evals/`, `tests/`, `scripts/`, `Makefile`. A correctly filled `.env` will still fail the record phase with "DEEPGRAM_API_KEY is unset". Export the variables in the shell instead. Note `.env` also sets `TS_LLM_MODE`, so auto-loading it would let a local file silently flip a judge's replay run into live mode — the fix is to export keys, not to add `load_dotenv()` blindly. `docs/REPRODUCTION.md` §10 was corrected. |

## Open — required deliverables and scoring

| # | Risk | Status | What to do |
|---|---|---|---|
| 12 | 4 of 12 eval cases exist, all on the synthetic scaffold fixture | **OPEN — blocks Measured Improvement (15 pts)** | Downstream of #2. Hand-writing fixtures to contain the phenomena being graded would be grading against a script. `make eval` banners any non-`capture` fixture as NOT A REPORTED RESULT. Per-case status in `evals/DATA.md`. |
| 20 | No product-agent trajectory exists for any of the three systems | **OPEN — required deliverable** | Downstream of #2. Needs `audience_signal_agent`, `baseline_single_prompt`, `baseline_chat_only`. Status table in `trajectories/README.md`. |
| 6 | Video not started; ≤5:00 and a hard deliverable | **OPEN** | Monday 14:00–16:00 MSK reserved; storyboard in `../notes/06-VIDEO.md`. Needs footage from #2. If the schedule slips, cut the video before the frontend — a judge who cannot watch the demo cannot score End-to-End Quality at all. |
| 8 | Only the latest *complete* submission is evaluated | **OPEN** | Submit a complete draft early Monday, then revise. |
| 7 | Submission ownership under the Participation Agreement | **OPEN** | Read the actual agreement before uploading. |
| 13 | `legacy/frontend/` (180 KB) ships in the archive unless excluded | **OPEN — C-phase** | It fabricates names, emotes and cluster values. A judge who opens it sees generated data inside the submission. Exclude or delete before packaging. |

## Open — accuracy and hygiene

| # | Risk | Status | What to do |
|---|---|---|---|
| 14 | Twitch VOD retention figures (7 / 14 / 60 days by tier) come from planning notes, not a source | **OPEN — UNVERIFIED** | Carries the product's second thesis, so source it before it enters the README or the video. Currently stated qualitatively, with no numbers. |
| 15 | Jan/Mar 2026 per-message cost and tail-latency figures are team recollection | **OPEN — UNVERIFIED** | The README states the failure qualitatively and quotes no figure. A number for the video has to be re-measured, not recalled. Supersedes the old #9. |
| 11 | `requirements.txt` declared six packages nothing imports | **Fixed 2026-08-30** | Removed `deepgram-sdk`, `fastapi`, `uvicorn`, `python-dotenv`, `orjson`, `pydantic`, and `pytest-asyncio` (zero async tests). Proved rather than asserted: a clean venv built from the reduced file plus `-e .` runs the full suite green. The replay path is now one runtime package, `httpx`. A test fails the build if a declared package is never imported. |
| 35 | `make scan` reports a placeholder docs block as the project's highest-severity secret | **OPEN — new 2026-08-30** | `scripts/scan_secrets.py` treats `KEY=value` as a credential unless the value is empty or `<angle-bracketed>`. It does not recognise the `your_*` convention, so `legacy/README.original.md` — six lines of `DB_PASSWORD=your_password` — outranked the eight real credentials in `.env`. Cost: #16 sat as the top P0 for a full day. Add the placeholder form and re-run; the fix belongs with a test per form, like the #18 rewrite. |
| 5 | Vision model choice | **Partly resolved 2026-08-30** | `deepseek-v4-flash-vision-exp` is now chosen in `providers/vision.py`, and V4-Flash is documented as text-only. It has never actually been called, so schema compliance is unverified until B1. Captions are cached, so replay is unaffected either way. |

## Mitigated or fixed

| # | Risk | Status | Evidence |
|---|---|---|---|
| 3 | Judges cannot run live Twitch capture | **Mitigated, and now proved by execution** | Replay plus the committed model-call cache. 2026-08-30: C2's command list — `replay`, `baseline`, `eval` — is executed in the suite with every credential deleted from the environment and `socket.socket`, `create_connection` and `getaddrinfo` all rigged to raise. The chain completes on cache hits alone, and an unrecorded system exits 3 rather than reaching for a provider. A separate out-of-process test asserts `httpx` never even enters the module table of a replay run. The full C2 on recorded fixtures still waits on #2. |
| 4 | Frontend fabricates all data | **Mitigated for the shipped surface** | The dashboard renders only what `/api/replay` serves; a test fails the build on `Math.random` or an `innerHTML` assignment, and another requires every colour to exist in `DESIGN.md`. `legacy/frontend/` still fabricates — that is #13. |
| 10 | `python -m ts.cli` failed from a fresh clone | **Fixed 2026-08-30** | `pyproject.toml` declares the src layout; `make setup` runs `pip install -e .`. Verified with no `PYTHONPATH`. **Caveat:** the checked-out `.venv` was built by `uv` and has no `pip`, so the editable install was confirmed through `uv pip`; the literal `python3 -m venv` + `pip` path is only proven by the C2 fresh-clone run. |
| 18 | `make scan` gave false assurance for the whole project | **Fixed 2026-08-30** | Three defects at once: `grep -r .` on macOS never reached `.env`; the pattern list lived in the Makefile so it matched itself and was permanently red; `legacy/` was excluded while remaining in the tree. Replaced by `scripts/scan_secrets.py`, 10 tests including a regression for each. |
| 19 | `trajectories/product-agent/` held 55 test artifacts and no real trace | **Fixed 2026-08-30** | Removed; `TS_TRACE_DIR` redirects the suite so the class of problem cannot recur. A test rejects any trace whose case id is not a frozen case or a tiled window. |
| 9 | Pricing/latency figures from unsourced planning docs | Superseded | Split into the specific claims #14 and #15 rather than a general policy line. |
| 16 | `legacy/README.original.md` lines 18–23 hold live credentials | **Withdrawn 2026-08-30 — scanner false positive** | Read the file instead of trusting the scan: the lines are `DB_PASSWORD=your_password`, `DEEPGRAM_API_KEY=your_key`, `TWITCH_OAUTH=your_token`, inside a "Create `.env`:" instruction block. Placeholders, not credentials, so there is nothing to rotate and `legacy/` stays preserved as-is per `docs/PRE_EXISTING.md`. The scan is what needs fixing: `scan_secrets.py` recognises `<your key here>` and empty values as placeholders but not the `your_*` form, so it reports a six-line docs example as the highest-severity finding in the project. Left open as #35 — a scanner that cries wolf on its own README gets ignored, which is the failure mode #18 already cost this project once. |

## Environment

| # | Risk | Status | What to do |
|---|---|---|---|
| 23 | `make setup` cannot run on the development machine — `python3 -m venv` fails at `ensurepip` | **OPEN — blocks closing #10, not the project** | Verified 2026-08-30 on Homebrew Python 3.11 and 3.14: both fail with `ensurepip ... returned non-zero exit status 1`. The failure is upstream of anything this project controls, but it means the literal `make setup` line has never executed here, so #10's caveat cannot be closed locally. What *was* proved: a clean venv created with `uv`, installed from the reduced `requirements.txt` plus `pip install -e .`, runs all 154 tests green. `docs/REPRODUCTION.md` §2 documents the fallback. Confirm the stdlib path on a second machine at C2. |
| 24 | Two documents claimed a summary hierarchy that no module implements | **Fixed 2026-08-30** | `docs/ARCHITECTURE.md` listed it under "implemented nodes" and the README component table listed it unmarked among components that exist. Zero matches in `src/`. Both now mark it as a named, unbuilt gap; a test asserts the declaration stays in step with the tree. The README row was written on 2026-08-30 by carrying a design table over from `../notes/01-PRODUCT.md` without checking it against the code. |
| 25 | Twitch poll limits in `report/poll.py` (5 options, 60/25 chars) are recalled, not sourced | **OPEN — UNVERIFIED, low** | Nothing posts, so a wrong cap costs nothing today, and every trim is reported in the draft's `warnings` rather than applied silently. Check them against Twitch's API documentation before any real posting integration. |
| 26 | The provenance gate rejected every correct abstention | **Fixed 2026-08-30** | A `none` card claims nothing, so it cites nothing, so it failed on `E_NO_EVIDENCE`. Measured before the fix: a correct abstention scored `unsupported_rate = 1.0` — the headline metric — and landed in the dashboard's rejected block, so the demo would have shown the product's best moment as a failure. It also depressed cases 5, 11 and 12, the three the product is designed to win on. `none` now takes an abstention path that fails only on self-contradiction (citing messages or naming a cause), and a passing one is labelled `abstained`. 10 tests, including one that keeps the path from becoming a hole in the gate. |
| 27 | The provenance gate used an inclusive window end while every query path is half-open | **Fixed 2026-08-30** | `events.window` is `[start, end)` and the agent's tools follow it, but `check_card` accepted `<= end`. Demonstrated on the sample fixture: a message at exactly the tile boundary is invisible to window 1's tools, belongs to window 2, and the gate still verified a window-1 card citing it. Since tiles are adjacent, the gate was blind at every boundary to exactly the claim it exists to catch — understating the unsupported-card rate, the headline metric. Now half-open. Verified that all four frozen gold cards still pass, and a test keeps that true. |
| 28 | A one-word trigger quote satisfies the gate's verbatim check without proving causation | **OPEN — known limitation, deliberately not fixed** | `_token_overlap` measures the fraction of the *quote's* tokens found in the trigger text, so the shorter the quote the easier it is to satisfy: `"или"` passes against the sample transcript. A minimum quote length would close it, but the frozen metric definition says "does not appear verbatim", and tightening the rule after publishing the definition would make reported numbers incomparable to the metric they claim to be. Stated in README §11. Fix it in the next build, not mid-flight. |
| 29 | The gate verified cards citing a transcript segment or frame as a "representative message" | **Fixed 2026-08-30** | Evidence means chat messages; the gate accepted any event id, so a card could offer the streamer's own speech as the audience's response to it and pass with no violations. Two new codes, `E_EVIDENCE_NOT_A_MESSAGE` and `E_CIRCULAR_EVIDENCE`. All four frozen gold cards still pass, asserted by test. |
| 30 | The reducer silently deleted every emote-only message | **Fixed 2026-08-30** | `canonical` stripped `[^\w\s]+`, which removes symbols as well as punctuation, so `😂😂😂` canonicalised to nothing and `reduce_chat` dropped it. On Twitch that is the most common reaction there is, and the module's own docstring claims counts are preserved. Measured before the fix: 5 messages in, 4 lost, burst counts summing to 1. Punctuation is now stripped by Unicode category so symbols survive, and a punctuation-only message goes to a counted `∅` bucket instead of vanishing. Verified the scaffold fixture reduces identically — 32 → 15 bursts, ratio 0.469 — so nothing frozen moved. |
| 31 | Trigger accuracy — metric A — could not be lowered by emitting noise, and the README stated a definition the code did not implement | **Fixed 2026-08-30** | Measured: one correct card plus nine hallucinations reported trigger accuracy 1.0. The denominator is matched cards, not "the cards emitted" as README §6 claimed. The denominator is kept — gold is not exhaustive on twelve cases, so a real signal nobody labelled would otherwise score as a wrong trigger — but the README now says what is computed, and `unmatched_rate` is reported beside it and in `comparison.csv`. That probe now reads 1.0 / 0.9. Nothing had been measured yet, so the frozen protocol is intact. |
| 32 | The same gold signal could be matched by two cards | **Fixed 2026-08-30** | A system emitting one card twice had that single gold signal weighted twice in trigger accuracy. Matching is now one-to-one in emission order; the duplicate counts as unmatched. |
| 33 | The card cap existed only as a request in the prompt; neither system enforced it | **Fixed 2026-08-30** | Measured: a model returning ten cards had all ten kept, in the agent and in the baseline. `03-EVAL_DESIGN.md` promises the baseline "the same output schema and card cap", and an unenforced cap contaminates the comparison — a system that ignores it gets more chances at recall and more cards over which the unsupported rate is averaged. `cap_cards` now applies `MAX_CARDS = 3` in one place used by both, unknown types are dropped first so junk cannot fill the cap, and the number dropped is reported in the run document and the trajectory. |
| 34 | Tool calls beyond four per step were truncated without telling the model | **Fixed 2026-08-30** | To the model a silently dropped call is indistinguishable from a tool that returned nothing. The results payload now names how many calls were not executed and why. |
