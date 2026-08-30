# Submission — Twitch Agent

micro1 Frontier Engineering Challenge 2026. Everything a judge needs, in one place.

> Twitch Agent turns an unreadable live chat into a small number of verified audience signals: it
> links each cluster of answers, reactions, questions and warnings to the exact stream moment that
> caused it, and shows the evidence.

## Run it in two minutes, with no API keys

```bash
make setup PYTHON=python3.12     # needs CPython 3.10+; macOS system python3 is 3.9
make test                        # 523 passed, ~1 s
make eval                        # 48 cache hits, 0 API calls, $0.00
```

`make eval` reproduces every number below from the committed response cache. It was verified
from a clean clone with `.env` deleted and every credential unset. If a prompt, model or
temperature had been edited without re-recording, it would exit `3` rather than quietly call an
API.

Three routes, all keyless:

| route | what it is |
|---|---|
| `/` | the product — a recorded run replayed at its true cadence, chat on the left, signals on the right |
| `/method` | the evidence — comparison table, every card in three states, changelog, failure modes |
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

## Where everything is

| Deliverable | Path |
|---|---|
| Overview, problem, baseline, architecture, protocol, limitations | `README.md` |
| Reproduction, step by step, with runtimes and expected output | `docs/REPRODUCTION.md` |
| Improvement changelog: every repair with measured before/after | `docs/IMPROVEMENT_CHANGELOG.md` |
| Architecture diagram, one file per node, gaps marked | `docs/ARCHITECTURE.md` |
| Results table, per-case CSV, raw predictions with gate decisions | `evidence/` |
| Agent trajectories — 33 real runs, 11 cases × 3 systems | `trajectories/product-agent/` |
| Coding-agent disclosure (how this was built) | `trajectories/coding-agents/README.md` |
| Frozen cases, gold labels, fixture provenance | `evals/` and `evals/DATA.md` |
| Every decision with its rationale | `DECISIONS.md` |
| Open risks, ordered by severity | `RISKS.md` |
| Cost ledger — every paid call | `COST_LEDGER.md` |
| Pre-existing vs competition work | `docs/PRE_EXISTING.md` |
| Live capture (demo path, needs keys, costs money) | `src/ts/live.py`, `/api/live` |
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

1. **No video.** The only required deliverable that does not exist.
2. **Gold labels unconfirmed** (`evals/REVIEW_ME.md`).
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
