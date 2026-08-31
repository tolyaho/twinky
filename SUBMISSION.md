# Submission — Twinky, grounded audience signals from Twitch

micro1 Frontier Engineering Challenge 2026. Everything a judge needs, in one place.

> Twinky turns an unreadable live chat into a small number of verified audience signals: it
> links each cluster of answers, reactions, questions and warnings to the exact stream moment that
> caused it, and shows the evidence.

## Run it in two minutes, with no API keys

```bash
make setup PYTHON=python3.12     # needs CPython 3.10+; macOS system python3 is 3.9
make test                        # 688 passed, ~1 s
make eval                        # 48 cache hits, 0 API calls, $0.00
```

`make eval` reproduces every number below from the committed response cache. It was verified
from a clean clone with `.env` deleted and every credential unset. If a prompt, model or
temperature had been edited without re-recording, it would exit `3` rather than quietly call an
API.

Three routes, all keyless:

| route | what it is |
|---|---|
| `/` | the product — a recorded run replayed at its true cadence. Three zones: the raw chat flood, a board of grouped audience signals with their causes, and a rail of live statistics. `Replay \| Live` switches to a real channel's chat over anonymous IRC, keyless and free |
| `/method` | the evidence — comparison table, every card in three states, a generated agent graph, the read-only NEEDS A LOOK panel, changelog, failure modes |
| `/philosophy` | the argument, including the result that counts against the product |

See the product end to end on the strongest fixture:

```bash
F=evals/fixtures/stableronaldo_2026-08-30T0723
make replay   FIXTURE=$F         # agent over 13 windows, from cache
make baseline FIXTURE=$F         # the fair baseline, same windows
make debrief  FIXTURE=$F         # the post-stream artifact
make demo     FIXTURE=$F         # dashboard on http://127.0.0.1:8000
```

## The one case that makes the argument

`c01_word_puzzle_amethyst`, from a **sleep stream at 3:23 am**: three people asleep, an automated
word-guessing overlay running, and **zero speech in the entire 12-minute capture** — Deepgram
returned no utterances, which is correct.

The frame shows `GUESS THE WORD!` and `ame_______`. Chat types *amethyst, American, amendment,
amethysts*. As text those words are noise. Against the screen they are an answer distribution.
A chat-only system has no possible account of them, and neither does a speech-only system.

That is the whole thesis, and it is not a hypothetical: it is case 1 of 11.

## Results

Eleven frozen cases, four real broadcasts, one run, no tuning after the numbers were seen.

| system | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|
| **agent** | 23 | **0.500** | 0.913 | 0.739 | **0.182** |
| baseline — one prompt, same events | 21 | 0.000 | 0.952 | **0.619** | 0.091 |
| ablation — chat only, diagnostic | 25 | 1.000¹ | 0.960 | **0.280** | 0.091 |

¹ One matched card out of twenty-five — meaningless alone, which is why `unmatched` is beside it.

**The agent wins grounding and loses restraint.** It doubles the baseline's recall and is the
only system that ever names a correct cause; its unsupported-card rate is the worst of the three.
Both halves are reported. The full account, including a first run that was discarded rather than
published, is in `docs/IMPROVEMENT_CHANGELOG.md`.

## Three things that were tried, measured, and rolled back

The changelog carries three experiments that did not ship. Each was diagnosed from data, built,
measured against the frozen cases or frozen labels, and then declined — which is the part of
engineering that usually leaves no trace.

| experiment | measured | why it did not ship |
|---|---|---|
| **Louder audio** — the sleep stream was thought too quiet to transcribe, so it was amplified 28 dB and re-run | **zero** additional transcript segments | It turned a suspected pipeline bug into a verified property of the fixture |
| **Inlining the stream context** — the agent had never once named a frame caption, so the window's speech and screen events were put in its turn with their ids | Frame citations **0 → 4**, and abstentions **5 → 0**. Same recall, unsupported rate 0.739 → 0.882 | Handed candidates it stopped abstaining entirely, and picking one is how a card becomes scoreable and therefore wrong |
| **Embedding clustering** — measured as a third grouping arm against labels frozen in a commit containing no arm code | Best pooled F1 **0.583** vs the shipped arm's 0.403 — but the same threshold scores **0.770** on one window and **precision 0.164** on the other | The threshold does not transfer, and it was chosen by looking at the labels. It won on a metric the product is not bought on |

Both later experiments reproduce with no keys:

```bash
TS_LLM_MODE=replay python -m evals.run_eval --ablation --grounded --out evidence/grounded
TS_LLM_MODE=replay python -m evals.grouping.score_arms
```

## Grouping, evaluated rather than asserted

Chat grouping is the difference between one row saying `violet × 27` and twenty-seven rows saying
nothing. It is scored on **pair-level precision and recall** against intent labels for 164
messages across two windows — frozen, with a checksum, in a commit containing no arm code.

| arm | precision | recall | F1 |
|---|---:|---:|---:|
| exact canonical — what shipped first | **1.000** | 0.057 | 0.107 |
| **token + prefix — what ships now** | 0.926 | **0.257** | **0.403** |

Compression is deliberately **not** the metric: an arm that merges every message into one group
compresses perfectly and is useless. The labels are model-drafted and say so.

## Where everything is

| Deliverable | Path |
|---|---|
| Overview, problem, baseline, architecture, protocol, limitations | `README.md` |
| Reproduction, step by step, with runtimes and expected output | `docs/REPRODUCTION.md` |
| Improvement changelog: every repair with measured before/after | `docs/IMPROVEMENT_CHANGELOG.md` |
| Architecture diagram, one file per node, gaps marked | `docs/ARCHITECTURE.md` |
| Results table, per-case CSV, raw predictions with gate decisions | `evidence/` |
| Agent trajectories — **118 real runs**, written as each run happened | `trajectories/product-agent/` |
| Coding-agent disclosure (how this was built) | `trajectories/coding-agents/README.md` |
| Frozen cases, gold labels, fixture provenance | `evals/` and `evals/DATA.md` |
| Every decision with its rationale | `DECISIONS.md` |
| Open risks, ordered by severity | `RISKS.md` |
| Cost ledger — every paid call | `COST_LEDGER.md` |
| Pre-existing vs competition work | `docs/PRE_EXISTING.md` |
| Live **Tier 0** — a real channel's chat, grouped, **no key and no cost** | `src/ts/live_chat.py`, `/api/live_chat` |
| Live full pipeline (demo path, needs keys, costs money) | `src/ts/live.py`, `/api/live` |
| Grouping arms A/B/C scored on frozen pair labels | `evals/grouping/` |
| Video | *not recorded* |

## What is honest about this submission

- **No number here was not measured.** Nothing is estimated, extrapolated or rounded up from a
  plan. Where something was not measured, it says so.
- **A broken run was thrown away rather than reported.** The first eval had the baseline emitting
  zero cards across all eleven cases. `make eval` now prints `BROKEN — NOT A RESULT` and exits
  `5` if any system emits nothing, because that failure looks exactly like a result.
- **Nothing was tuned after seeing the score.** Every post-measurement change is labelled
  `repair` in `DECISIONS.md`, with its reason. There are no `tuning` entries. Two obvious
  score-raising changes were explicitly rejected and recorded as such.
- **Gold labels are model-drafted and not yet human-confirmed.** All eleven say
  `"reviewed": false`. `evals/REVIEW_ME.md` exists to change that in ten minutes. Claiming a
  review that did not happen would be the one unrecoverable mistake in an evaluation.
- **The git history is reconstructed.** The tree was never under version control; commit order is
  real, commit dates are assigned from the `PROGRESS.md` session log. Stated in `README.md` and
  `docs/PRE_EXISTING.md`.
- **The agent's main failure is documented with a case id**, not softened. On the very case above
  it returned "no clear speech or on-screen content detected" — having never called
  `get_frame_captions`. The trajectory shows it step by step.

## Known gaps

`make preflight` checks every item below that can be checked, in one command, and exits non-zero
while a hard blocker stands. It reports and never repairs.

1. **No video.** The only required deliverable that does not exist.
2. **The repository must be pushed before it is made public.** `origin/main` is behind local;
   publishing it as it stands would show an older project and would look finished.
3. **Gold labels unconfirmed** — `make review`, then `evals/REVIEW_ME.md`.
3. **Summary hierarchy not built.** A named gap in `README.md` §5 and `docs/ARCHITECTURE.md`,
   not a silent omission.
4. **No per-component ablation.** There was time for one honest end-to-end comparison, not five,
   so no component-level claim is made.
5. **`make capture` needs Python 3.10+ and two API keys.** It is not on the graded path;
   `make setup-record` installs its extras separately.
6. **Live capture is a demo path, not the graded one.** It needs keys and spends money per
   window, refuses to start past a $3.00 cap, stops itself after ten minutes, and records into a
   temporary cache so the committed reproduction cache is never touched. Replay remains the
   default and the documented route. Exercised once end to end against a live broadcast:
   113 messages, 3 cards, 104.8 s, ~$0.006.

Cost of every model call ever made in this project: **$0.43**, itemised in `COST_LEDGER.md`.
