# Twitch Agent

> A chat message is not text. It is a response to something. `10` is meaningless; `10` thirty
> seconds after *"how would you rate this game?"* is a rating. Chat is only interpretable against
> the stimulus that caused it — and the stimulus is in the audio and on the screen, not in the chat.

Twitch Agent turns an unreadable live chat into a small number of verified audience signals: it
links each cluster of answers, reactions, questions and warnings to the exact stream moment that
caused it, and shows the evidence.

## Status — read this first

Four fixtures captured from live broadcasts, eleven frozen evaluation cases, and one measured
end-to-end comparison. `make eval` reproduces every number below from the committed cache in
**79 ms, 48 cache hits, 0 API calls**, verified with every credential unset.

**The result is mixed and reported as such.** The agent doubles the baseline's signal recall and
is the only system that ever names a correct cause; it also has the worst unsupported-card rate
of the three. Neither prompt was edited after the numbers were seen — see
`docs/IMPROVEMENT_CHANGELOG.md` for the full account, including the run that was discarded and
why.

Nothing in this repository states a number that was not measured. Gold labels are model-drafted
and not yet author-confirmed (§6).

---

## 1. Problem and intended user

A mid-to-large streamer or their operator: thousands of concurrent viewers, tens of chat messages
per second, a handful of volunteer moderators. They read perhaps a low single-digit percentage of
chat during a broadcast, and the platform deletes the VOD — and the chat replay with it — within
weeks of the stream ending.

Two things are lost. Live, the audience is answering questions the streamer asked aloud and
nobody can read the answers. Afterwards, the record of what the audience said is gone.

## 2. Value and the current bottleneck

The bottleneck is not volume, it is **grounding**. `10`, `left`, `лес` are meaningless as text.
They are only interpretable against the stimulus that caused them, and the stimulus is in the
audio and on the screen. A chat-only tool can cluster messages; it structurally cannot tell you
what they were a response to, and therefore cannot tell you whether a question was answered.

That is why the system is multimodal. Not sophistication for its own sake: it is the minimum
required for chat to mean anything at all.

## 3. Baseline

One direct prompt receiving **the same raw events** the final system sees — chat, final
transcript segments, frame captions, ids and timestamps — with the same output schema and the
same card cap. No tools, no reduction, no rolling state, no verifier, no memory.

A chat-only run exists as a diagnostic ablation (`--chat-only`), never as the headline baseline.
Comparing a multimodal agent against a chat-only prompt would measure the value of giving the
system more data, not the value of the agentic workflow.

Baseline results, 11 cases: **21 cards, trigger accuracy 0.000, unmatched 0.952, unsupported
0.619, recall 0.091.** It attributes to speech readily — fifteen of twenty-one cards name a
transcript segment — but nine are rejected on `E_TRIGGER_LATE`: seeing the window flat, it picks
a plausible line without checking that the cause precedes the effect.

## 4. Final agent workflow

```
capture → reduce → [ agent: tools ⇄ model ] → provenance gate → verified cards → debrief
```

The agent is a real agent: the model decides which context it needs, calls bounded tools, sees
the results and decides again, up to four steps. The controller executes the tools, enforces the
schema and the time windows, and then runs a deterministic provenance gate over whatever the
model finally produced.

Tools, all time-bounded: `group_repeated`, `get_transcript_window`, `get_frame_captions`,
`get_chat_window`.

Exactly one outward action exists — approve → draft poll — and it never posts automatically.

## 5. Architecture and purposeful design choices

Full diagram and node status: `docs/ARCHITECTURE.md`. Every choice with its rationale:
`DECISIONS.md`.

| Component | The failure it fixes | Built |
|---|---|---|
| Speech + frame context | Short chat replies are meaningless as text (observed Sept 2025 – Jan 2026) | yes |
| Event-centric grouping | Embedding clustering gave unstable clusters (Oct 2025; again Mar 2026) | yes |
| Deterministic reducer | Per-message inference was too slow and too expensive at scale (Jan, Mar 2026) | yes |
| Provenance gate + abstention | Cards attaching to nothing, noted in the team's own testing 4 Jan 2026 | yes |
| Replay + response cache | Live streams are not reproducible and judges have no API keys | yes |
| Summary hierarchy (1m/5m/30m/2h) | A long stream does not fit one context window | **no** |

The summary hierarchy is a real part of the product thesis and is not implemented. Fixtures run
2–12 minutes and analysis windows are sixty seconds, so nothing in the evaluation exercises it.
It is listed as a named gap rather than left out, because leaving it out would make the design
look smaller than it is and listing it unmarked would claim work that does not exist.

Three things were deliberately **not** built: a web-search agent, a scheduler agent, and a second
signal agent. None addresses a demonstrated failure. No LangChain and no LangGraph either — they
build prompts we do not control, and a version bump silently changes their formatting, which
changes the cache key, which breaks keyless reproduction. That property is a qualification gate,
so the prompt string has to be ours. The agent loop is about sixty lines.

## 6. Evaluation protocol

Two primary metrics, chosen so a reader understands them in five seconds:

- **Trigger accuracy** — of the cards that *match a gold signal*, the fraction naming the correct
  causing event, *or correctly returning `unknown`* where the fixture has no supported cause.
  Needs gold labels. The denominator is matched cards rather than every card emitted, because
  gold is not exhaustive on eleven cases and a real signal nobody labelled would otherwise score
  as a wrong trigger. The cost of that choice is that noise cannot lower it, so it is always
  reported beside **unmatched rate** — the fraction of emitted cards matching no gold signal.
  Measured on a probe: one correct card plus nine hallucinations still reports trigger accuracy
  1.0, and unmatched rate 0.9.
- **Unsupported-card rate** — the fraction of cards whose evidence fails deterministic
  validation: a cited message id that does not exist, a cited message outside the claimed window,
  or a quoted trigger absent from the transcript span it claims. **No gold labels needed**, so it
  runs over every fixture for free.

Both systems receive identical windows and are scored on **every card they emit**, verified and
rejected alike. Scoring only the cards that survived the gate would force the unsupported rate to
zero for both systems by construction.

Case matrix and per-case status: `evals/DATA.md`. **Eleven cases are frozen, all against real
captures from four broadcasts**, including all three the product is designed to win on: warning
with no provable cause, sarcasm, and abstention. Across 12 gold signals: 4 frame triggers,
2 speech triggers, 5 `unknown`, 1 abstention.

**Gold labels were drafted with model assistance from the captured fixtures. Per-case review
status is tracked in `evals/REVIEW_ME.md`, and at the time of writing all eleven are still
`"reviewed": false` — no human has confirmed them.** Saying they were "reviewed by the author"
would be the easy sentence and it would not be true, so it is not written here; the flag in each
gold file is the source of truth and `REVIEW_ME.md` is a ten-minute pass built to change it. The labels
are not hand-typed: every id is resolved from the fixture, and `tests/test_frozen_cases.py`
pushes each gold signal through the real provenance gate, because a gold label that cannot pass
the gate scores every correct card as a silent miss.

## 7. Results and evidence

Eleven cases, four broadcasts, one run, no tuning after the fact.

| system | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|
| **agent** | 23 | **0.500** | 0.913 | 0.739 | **0.182** |
| baseline — single prompt, same events | 21 | 0.000 | 0.952 | **0.619** | 0.091 |
| ablation — chat only, diagnostic | 25 | 1.000¹ | 0.960 | **0.280** | 0.091 |

¹ One matched card out of twenty-five. Meaningless alone, which is why `unmatched` sits beside
it — this is the degenerate case that metric exists to expose.

The agent wins grounding and loses restraint. It is the only system that names a correct cause,
at double the baseline's recall, and it makes more unsupported claims doing it. The chat-only
ablation wins the headline metric by having nothing to attribute to, so it abstains — see the
hot take in §11.

| artifact | what it holds |
|---|---|
| `evidence/report.md` | the table above plus the provenance of every fixture behind it |
| `evidence/comparison.csv` | one row per case per system |
| `evidence/predictions.json` | raw predictions, gate decisions and trace id for every case |
| `trajectories/product-agent/` | one trajectory per system per case, written as the run happens |
| `docs/IMPROVEMENT_CHANGELOG.md` | every repair with its measured before/after, and the discarded run |

## 8. Improvement changelog

`docs/IMPROVEMENT_CHANGELOG.md` — every entry measured on the frozen eval set, including the
removed experiment and its measured result.

## 9. Reproduction

`docs/REPRODUCTION.md`. `make test`, `make baseline`, `make replay` and `make eval` run with **no
API keys**, from the committed content-addressed response cache.

## 10. Agent and tool disclosure

- **In the product:** one agent, `audience_signal_agent`, `gpt-4.1-nano`, `temperature=0`,
  `max_tokens=900`, `max_steps=4`, four bounded read-only tools. The baseline and the chat-only
  ablation use the same model and the same card contract. Vision captions come from
  `gpt-4.1-mini`; speech from Deepgram Nova-3 (`nova-3-general`). Both are record-mode only.
  These are the models the committed cache was recorded with, and they are the defaults in code,
  so a clone with no environment reproduces every number.
- **In building it:** Claude Code on Claude Opus 5, run as a scheduled loop that took one
  ladder item per iteration. Full disclosure table, method and the defects the sessions
  found: `trajectories/coding-agents/README.md`.

## 11. Known limitations, main failure mode, hot take

**Limitations.** Windows are fixed 60-second tiles, so a signal spanning a tile boundary can be
split. Diarization errors propagate into trigger attribution. The reducer collapses on exact and
near-exact repeats, so a paraphrased flood still costs tokens. Only one language pair has been
exercised.

The provenance gate has a known soft spot: a very short trigger quote is trivially verbatim. One
common word lifted from the transcript satisfies the quote check without demonstrating that the
event caused anything. Enforcing a minimum quote length would fix it, and it is deliberately not
done here — the frozen metric definition says "does not appear verbatim", and tightening the rule
after the definition was published would make the reported numbers incomparable to the metric
they claim to be. It is recorded in `RISKS.md` #28 instead.

**Main failure mode, measured.** The agent names a chat message as the cause of the chat it is
explaining. Fourteen of its twenty-three cards set `trigger.event_id` to a chat UUID and eight
are rejected on `E_CIRCULAR_EVIDENCE` — the largest single source of its unsupported rate.

The sharpest instance is `c01_word_puzzle_amethyst`: the screen shows `GUESS THE WORD!` with
`ame_______` and chat answers *amethyst / American / amendment*. The agent called
`group_repeated` and `get_transcript_window`, found no speech, and returned a `none` card reading
*"no clear speech or on-screen content detected"* — **without ever calling `get_frame_captions`**.
It declared the screen empty without looking at it, on the one case where the screen is the only
possible cause. The trajectory shows this step by step. The fix is obvious and was deliberately
not applied: changing the prompt after seeing the score is tuning, and it would invalidate this
comparison.

The baseline fails differently — nine of twenty-one cards rejected on `E_TRIGGER_LATE`, naming a
spoken line that occurs *after* the messages it supposedly caused.

**Hot take.** The evaluation produced a result that argues against the product, and it is the
most interesting number here: **the chat-only ablation — the system with the least information —
won the headline metric**, 0.280 unsupported against the agent's 0.739. It won by abstaining.
With no transcript and no captions it had no candidate causes to name, so it correctly returned
`unknown` eighteen times out of twenty-five, and an abstention is always gate-clean.

So an unsupported-card rate cannot be read alone: it is minimised by saying nothing. That is not
a flaw in the metric so much as the shape of the problem. Grounding is not summarization with a
better prompt; it is retrieval and proof, where the honest answer is often *"I cannot show you
the cause."* The agent is the only system here that named a correct cause at all, and it paid for
that by being wrong more often. Moving recall without buying it in unsupported claims is the
whole game, and this run says we have not won it yet.

The older objection still stands and is worth stating: top streamers do not read chat and do not
want a tool that reads it for them. That is right, and it is not what this is. The pitch is
*recover what you are structurally unable to see, and what the platform is about to delete.*
Livestreaming is the only creator medium whose artifact is designed to evaporate, and the second
half of this product is memory.

## 12. Video and trajectories

- Video: `[TBD]` — not yet recorded. This is the one deliverable below that does not exist.
- Trajectories: `trajectories/` — **33 real runs**, 11 frozen cases × 3 systems, written
  during the measured run and reproducible from the cache.

---

## Pre-existing work disclosure

This project began in September 2025 and was developed by three people until March 2026. Work
committed before **28 Aug 2026 15:00 UTC** is pre-existing and is listed in
`docs/PRE_EXISTING.md`. Competition work is everything after that timestamp, and every entry in
`docs/IMPROVEMENT_CHANGELOG.md` is measured on the frozen eval set in `evals/`.

### Git history disclosure

> This repository was created on 30 Aug 2026 from a tree that was never under version control.
> Its history is reconstructed: each commit holds the final state of the files it touches, and
> commit dates are assigned, not observed. The order is real; the dates are not. `PROGRESS.md`
> timestamps are real.

Concretely: a file first committed on 29 Aug already contains fixes made on 30 Aug, because no
intermediate snapshot of it exists to commit. Commit timestamps were taken from the session log
in `PROGRESS.md` so that the history and the written record agree and can be checked against
each other.

## Quick start (no API keys needed)

```bash
make setup
make test
```

`make demo` serves three routes, all without keys: `/` replays a recorded run at its true
cadence, `/method` holds the evidence, `/philosophy` states the argument including the result
that counts against the product. A live-capture demo path exists behind an explicit click; it
needs keys, spends money, and is capped and time-limited — replay is the default and the
documented route.

Full guide, including what currently exits `3` and why: `docs/REPRODUCTION.md`.
