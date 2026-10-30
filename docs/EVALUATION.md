# Evaluation — baseline, protocol and evidence

These sections were moved verbatim from `README.md` to keep the README short. The results table
itself stays at the top of the README; `evidence/summary.json` is its source, written by
`make eval`. The main failure mode, the hot take and the rolled-back experiments are still in the
README.

## Baseline

One direct prompt receiving **the same raw events** the agent sees — chat, final
transcript segments, frame captions, ids and timestamps — with the same output schema and the
same card cap. No tools, no reduction, no rolling state or memory. The same deterministic gate is applied afterward.

A chat-only run exists as a diagnostic ablation (`--chat-only`), never as the headline baseline.
Comparing a multimodal agent against a chat-only prompt would measure the value of giving the
system more data, not the value of the agentic workflow.

Baseline results, 11 cases: **21 cards, trigger accuracy 0.000, unmatched 0.952, unsupported
0.619, recall 0.091.** It attributes to speech readily — fifteen of twenty-one cards name a
transcript segment — but nine are rejected on `E_TRIGGER_LATE`: seeing the window flat, it picks
a plausible line without checking that the cause precedes the effect.

## Evaluation protocol

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
captures from four broadcasts**, including three cases the product is intended to handle: warning
with no provable cause, sarcasm, and abstention. Across 11 gold signals: 4 frame triggers,
2 speech triggers, 5 `unknown`, plus 1 must-abstain case.

**Gold labels were drafted with model assistance from the captured fixtures. Per-case review
status is tracked in `evals/REVIEW_ME.md`, and at the time of writing all eleven are still
`"reviewed": false` — no human has confirmed them.** Saying they were "reviewed by the author"
would be the easy sentence and it would not be true, so it is not written here; the flag in each
gold file is the source of truth and `evals/REVIEW_ME.md` is a ten-minute pass built to change it
(`make review`). The labels are not hand-typed: every id is resolved from the fixture, and
`tests/test_frozen_cases.py` pushes each gold signal through the real provenance gate, because a
gold label that cannot pass the gate scores every correct card as a silent miss.

## Results and evidence

Eleven cases, four broadcasts, one run, no tuning after the fact. The table is
[at the top of the README](../README.md#results-at-a-glance).

The agent has double the baseline's recall, and it now edges the baseline on unsupported claims
as well — 0.609 against 0.619, after the gate stopped rejecting a category the original product
allowed (see [the gate](../README.md#the-provenance-gate)). The chat-only ablation still wins
the headline metric by having nothing to attribute to, by not attempting concrete causal attribution; it still fails the must-abstain case — see the
[hot take](../README.md#main-failure-mode-and-hot-take) in the README.

*Correction.* Earlier versions of `README.md` said the agent "is the only system that names a
correct cause". `evidence/comparison.csv` and `evidence/predictions.json` do not support that.
The agent's single correct trigger is a correctly returned `unknown` on `c11_sarcasm_mockery`.
The ablation also scores one correct `unknown`, on `c10_spam_collapse`. No matched card from any
system names the gold speech or frame event. The same sentence appeared in
`docs/IMPROVEMENT_CHANGELOG.md`, `RISKS.md` #38 and the served `/method` and `/philosophy` pages.
Those were corrected on 2026-10-29; the changelog keeps its original entries with a dated
correction note under each.

| artifact | what it holds |
|---|---|
| `evidence/report.md` | the results table plus the provenance of every fixture behind it |
| `evidence/comparison.csv` | one row per case per system |
| `evidence/predictions.json` | raw predictions, gate decisions and trace id for every case |
| `trajectories/product-agent/` | one trajectory per system per case, written as the run happens |
| `docs/IMPROVEMENT_CHANGELOG.md` | every repair with its measured before/after, and the discarded run |


## Gate comparability and replay preservation

The canonical table uses `reaction-v2`. The original H1 report uses `strict-v1`: its unsupported
1.000 rescored to 0.200 with identical raw cards. See [GATE_VERSIONS.md](GATE_VERSIONS.md).
The gate checks citation/time consistency, not semantic causal correctness. A passing short
quote, unknown trigger, plausible title or model distribution does not establish a true cause.
Dashboard raw results predate this rule change; the viewer now applies the current gate in
memory and labels the source SHA/version. Existing frozen artifacts and real timing remain intact.
Two case pairs overlap in time; no labels are human-confirmed, so uncertainty is substantial.
