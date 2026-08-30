# Improvement changelog

Baseline → iterations → final. Every row carries evidence and a kept/revised/removed decision.

All competition numbers come from `evidence/report.md`, reproduced by `make eval` from the
committed cache in **79 ms with 48 cache hits and 0 API calls**, verified with every credential
unset. Eleven frozen cases across four real broadcasts; case matrix in `evals/DATA.md`.

## Pre-existing research (Sept 2025 – Mar 2026) — NOT competition work

Context for why the competition baseline is shaped the way it is. Not counted as measured
hackathon improvement.

| Period | What was learned | How it shapes the competition entry |
|---|---|---|
| Sept 2025 | Local CPU STT accumulated lag; Deepgram was accurate and ~$0.6/hr | Hosted streaming STT, capture-then-replay |
| Oct 2025 | Lexical embedding clustering gave unstable clusters; context conditioning raised cosine similarity from 0.784 to 0.935 on a probe pair | Motivates event-centric grounding over similarity clustering |
| Jan 2026 | Per-message reason extraction worked but cost ~$0.05 / 5 min on an active chat and had a long latency tail (median ~1s, mean ~7s, ~30s under load) | Motivates the deterministic reducer and event-centric batching |
| Jan 2026 | Observed failure: generated clusters sometimes attached to no real cause | Motivates the provenance gate and abstention — and metric B |
| Mar 2026 | `gpt-4.1-mini` 10–30s vs `gpt-4.1-nano` 1–3s | Latency-first model selection |
| Mar 2026 | Multi-agent/RAG sketch produced a working prototype but no measured benefit | Scoped out; see removed experiments |

## The measured result

| system | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|
| agent | 23 | **0.500** | 0.913 | 0.739 | **0.182** |
| baseline (single prompt, same events) | 21 | 0.000 | 0.952 | **0.619** | 0.091 |
| ablation (chat only, diagnostic) | 25 | 1.000¹ | 0.960 | **0.280** | 0.091 |

¹ One matched card out of twenty-five. Reported only because `unmatched` is printed beside it;
on its own it would be meaningless. This is exactly the degenerate case the unmatched rate was
added to expose.

**The agent wins on grounding and loses on restraint.** It doubles the baseline's signal recall
and is the only system that ever names a correct cause, and its unsupported-card rate is the
worst of the three. Both halves are reported; neither prompt was edited after seeing them.

## Competition iterations (28–31 Aug 2026)

Every row below is a repair to the measuring apparatus, not a quality tweak. The first eval run
produced numbers that were broken rather than bad, and the work was to make the comparison exist.

| Stage | What was tried and why | Evidence / result | Decision |
|---|---|---|---|
| First measured run | Ran all three systems over the 11 frozen cases | baseline **0 cards across 11 cases**; agent unsupported **0.95**, trigger **0.00** | **Discarded, not reported.** Zero cards is a parse failure, not a weak baseline |
| Repair 1 — baseline prompt | The baseline imported the *agent's* system prompt, a tool-calling protocol. Having no tools it replied `{"action":"call_tools"}`, and `.get("cards", [])` turned that into a clean empty list | baseline **0 → 21 cards** | Kept. Card contract is now one string included verbatim by both systems, asserted by test |
| Repair 2 — state the trigger rule | The gate rejected chat-as-cause and self-citation; the prompt never said so | agent `E_CIRCULAR_EVIDENCE` **19/20 (95%) → 8/23 (35%)**; unsupported **0.95 → 0.739** | Kept. Identical wording went to the baseline, so the fix is symmetric |
| Repair 3 — label citable ids | Input lines led with a bare bracketed timestamp, so every system cited the timestamp as the event id and was rejected on `E_UNKNOWN_MSG` | baseline now names a transcript segment in **15/21** cards instead of citing a number that does not exist | Kept. Affects the baseline only — the agent reads ids from JSON tool results — so this repair *strengthens the comparison against us* |
| Repair 4 — default to the recorded model | The model name is part of the cache key, and the default was a model no run was ever recorded with | `make eval` from a clean environment: **0 hits / 44 misses → 48 hits / 0 misses** | Kept. This was the reproducibility gate silently failing for everyone but the author |
| Repair 5 — a malformed reply no longer discards the valid cards beside it | `cap_cards` raised `AttributeError` on `{"cards": ["text", {...}]}`, so one bad entry threw away the whole reply — and crashed the agent's run outright, mid-record, after earlier windows had been paid for | baseline **20 → 21 cards**, unsupported **0.600 → 0.619** | Kept, and it moved a published number. Declared here rather than quietly re-run: it makes the baseline slightly *worse* on the headline metric and so narrows the gap against us, which is the only direction a post-hoc repair may move a result unchallenged |
| Reducer, tools, gate | Present in the final system | **Not independently ablated** | No per-component claim is made. There was time for one honest end-to-end comparison, not five |

**Largest single contributor:** Repair 1. Without it there was no baseline, therefore no
comparison, therefore nothing to measure. Every other number in this file is downstream of it.

## An iteration that was proposed, checked, and not made

**Hypothesis:** the agent's `E_CIRCULAR_EVIDENCE` failures come from an under-specified shared
contract — the prompt says "never invent a cause" but never says a trigger must be a speech or
frame event. One sentence in the shared spec would change all three systems identically, which
would be repair rather than asymmetric tuning.

**Checked before writing it.** The sentence is already there, added as Repair 2 above:

> `trigger.event_id` is what CAUSED that chat, so it is a SPEECH id (a transcript segment) or a
> SCREEN id (a frame caption). It is NEVER a chat id, and never an id that also appears in
> `evidence` — a message cannot be its own cause.

Verified in the cache rather than in the source: **129 of the 173 recorded text requests carry
that rule**, and the 44 that do not are the discarded first run. Every request behind the
published table was sent with it.

**What the residual failures actually are.** All eight surviving `E_CIRCULAR_EVIDENCE` cards set
`trigger.event_id` to a chat UUID *that also appears in their own evidence list* — the exact
thing the two clauses above forbid. Three of them additionally set `trigger.kind` to `"unknown"`
while naming a concrete id, which contradicts the same paragraph. These are not ambiguities being
exploited; they are stated rules not being followed by `gpt-4.1-nano`.

**Decision: no change, no re-measure.** The specified repair is already applied and its effect is
measured — `E_CIRCULAR_EVIDENCE` 19/20 → 8/23, unsupported 0.95 → 0.739. Any *further* change
aimed at those eight cards would be chosen after seeing the score and would lower the agent's
headline metric, which is the definition of tuning. Enforcing the rule in the controller the way
`cap_cards` enforces the card cap is defensible in principle and was rejected for the same reason:
the agent names a chat trigger 14 times to the baseline's once, so a "symmetric" guard would be
asymmetric in effect. Recorded in `RISKS.md` #38 as model behaviour rather than a contract defect,
and left for the next build, where it can be measured on a fresh run instead of retrofitted to
this one.

## Removed experiments, with their measured results

| Experiment | Measured result | Outcome |
|---|---|---|
| +28 dB gain on `stableronaldo` audio before transcription | **0 additional transcript segments** (0 before, 0 after) | Reverted, original audio retained. Confirmed the window contains no speech rather than inaudible speech — the streamer is asleep. Turned a suspected pipeline bug into a verified property of the fixture, and made it the strongest case in the set |
| Six declared dependencies nothing imported (`fastapi`, `uvicorn`, `pydantic`, `orjson`, `python-dotenv`, `deepgram-sdk`) | Clean venv from the reduced file ran the full suite green | Removed. The replay path is now one runtime package, `httpx` |
| Multi-agent + RAG sketch (pre-existing) | Working prototype, no measured benefit | Not carried into the competition entry |

## Main failure mode

**The agent names a chat message as the cause of the chat it is explaining.** Fourteen of its
twenty-three cards set `trigger.event_id` to a chat UUID, and eight are rejected outright on
`E_CIRCULAR_EVIDENCE` — the single largest source of its unsupported rate.

Concretely, `c01_word_puzzle_amethyst`: the frame shows `GUESS THE WORD!` with `ame_______` and
chat answers *amethyst / American / amendment*. The agent called `group_repeated` and
`get_transcript_window`, found no speech, and returned a `none` card reading *"no clear speech or
on-screen content detected"* — **without ever calling `get_frame_captions`**. It declared the
screen empty without looking at it, on the one case where the screen is the only possible cause.

The fix is obvious and was deliberately not applied: forcing a frame check after seeing the score
is tuning, and it would invalidate the comparison. It is the first thing to change in the next
build, and the correct measurement of it is a fresh run, not this one.

The baseline fails differently: nine of its twenty-one cards are rejected on `E_TRIGGER_LATE`. Seeing
the whole window flat, it picks a plausible-sounding line without checking that the cause precedes
the effect. Neither system had trouble producing fluent cards. Both had trouble proving them.

## Hot take

> The hard part of live-chat intelligence is not summarization. It is proving which stream event
> caused which audience signal — and knowing when the evidence is insufficient.

The evaluation produced a result that argues against the product, and it is the most interesting
number in this repository: **the chat-only ablation — the system with the least information —
won the headline metric.** Unsupported rate 0.280 against the agent's 0.739.

It won by abstaining. Having no transcript and no captions, it had no candidate causes to name,
so it correctly returned `trigger: "unknown"` in eighteen of twenty-five cards, and an abstention
is always gate-clean. Give a system more context and it starts making claims; claims can be
wrong, and this one measures wrongness.

Two things follow. First, an unsupported-card rate cannot be read alone — it is minimised by
saying nothing, so it belongs beside recall and trigger accuracy, where the ablation's 0.091 and
its single matched card tell the rest of the story. Second, this is the real shape of the
problem: grounding is not a summarization task with a better prompt, it is a *retrieval and proof*
task where the honest answer is often "I cannot show you the cause." The agent is the only system
here that named a correct cause at all, and it paid for that by being wrong more often. That
trade is the product, and the next build should be measured on whether it can move recall without
buying it with unsupported claims.

---

## Removed experiment #2 — inlining the stream context did not work

**Diagnosis first, from the recorded cache rather than from intuition.** `CARD_CONTRACT` demands
that `trigger.event_id` be a SPEECH or SCREEN id and states that every cited id must be one the
model "actually saw in the input". It was shown none. All **57** of the agent's own recorded
opening turns contain zero event ids — the whole turn is *"Analyse the window start_ms=… end_ms=…
/ Call tools to see what happened, then answer."* Across the **70** cached conversations that
reached a tool result, chat appeared in **70 (100%)** and frame captions in **2 (3%)**. In 97% of
conversations the only ids the model had ever been shown were chat ids, so naming a chat message
was the only move available to it. That is logged failure #39, and it made
`E_CIRCULAR_EVIDENCE` a missing input rather than a disobedient model.

**The fix.** A second arm, `agent_grounded`, puts the window's transcript segments and frame
captions into the opening turn as `id=… ts=… | text`, capped at 12 and 6, names that list as the
only source of trigger ids, and keeps `unknown` explicitly available. Nothing else changes: same
schema, same tools, same gate, same scorer, `temperature=0`. It is a **separate arm**, not a
re-recorded agent, because the prompt is the cache key and the committed cache is how a judge
reproduces every published number with no API key.

**Measured on the same eleven frozen cases, same windows, same gold labels:**

| system | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|
| agent | 23 | **0.500** | 0.913 | **0.739** | 0.182 |
| `agent_grounded` | 17 | 0.000 | **0.882** | 0.882 | 0.182 |
| baseline | 21 | 0.000 | 0.952 | 0.619 | 0.091 |

**It lost.** Same recall, worse unsupported rate, worse trigger accuracy. The change is not
adopted; `agent` remains the published system and its numbers are unchanged.

**But it did the thing it was built to do, and the mechanism is the finding.** Where each arm's
trigger id actually came from:

| | abstained | a chat id | a real transcript id | a real frame id |
|---|---:|---:|---:|---:|
| agent | 5 | 14 | 4 | **0** |
| `agent_grounded` | **0** | 12 | 1 | **4** |

Failure #39 is fixed in the narrow sense: the agent had never once named a frame caption, and
this arm names four. On the frame-only case `c07`, the published agent emitted three cards
reading *"Audience mentions 'draconic'"*, each naming a chat UUID as a `speech` trigger; the
grounded arm emitted one card titled *"Audience is guessing words related to 'dragon' and
'dracula'"* with `trigger.kind=screen`, a real frame id, and the quote `draco___`. It still
failed the gate — but on `E_TRIGGER_LATE`, having named a real screen event that came *after* the
chat it explained, which is a different and much more tractable error than inventing a cause.

**What killed it was abstention.** The agent returns `unknown` five times; the grounded arm
returns it **zero** times. Handed a list of candidates, it always picked one, and picking one is
how a card becomes scoreable and therefore wrong. `E_CIRCULAR_EVIDENCE` went *up*, 8 to 10.

This is the same trade the headline result already exposed, running in the opposite direction:
the ablation won by knowing less and saying nothing, and this arm lost by knowing more and always
committing. Supplying candidates without also teaching the model when *none of them* is the cause
just moves the failure from "invents a cause" to "picks the nearest one". That is the next
experiment, and it is not one to design after seeing this score.

Reproduce it with no keys and no cost:

```
TS_LLM_MODE=replay python -m evals.run_eval --ablation --grounded --out evidence/grounded
```

70 cache hits, 0 misses, $0.00. Recording it cost **$0.0122** (22 calls, 107,546 input and 3,589
output tokens at `gpt-4.1-nano` list price), logged in `COST_LEDGER.md`.
