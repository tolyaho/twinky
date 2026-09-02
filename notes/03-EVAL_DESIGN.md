# Evaluation design

## Why not GS-F1

The earlier plan proposed Grounded Signal F1 requiring four simultaneous conditions for a true
positive. On 10–12 cases that produces near-zero, unstable numbers for both systems, is hard to
debug, and is illegible when explained out loud. Rejected in favour of two metrics a reader
understands in five seconds.

## Primary metric A — trigger accuracy

Of the cards emitted, the fraction naming the correct causing event, **or correctly returning
`unknown`** where the fixture has no supported cause.

Requires gold labels. 10–12 cases.

## Primary metric B — unsupported-card rate

Fraction of cards whose evidence fails validation:

- a cited `message_id` does not exist, or
- a cited message falls outside the claimed window, or
- the quoted trigger does not appear verbatim in the transcript span it claims.

**Fully deterministic. No gold labels needed.** Therefore it runs over every fixture, unlimited,
free. It measures precisely the failure mode the team identified on 4 Jan 2026 ("sometimes the
clusters don't attach to anything"), and it is the metric the provenance gate is designed to move.

This is the highest-leverage simplification in the whole plan: annotation effort drops from
14 cases × 5 fields to 12 cases × 2 fields, and one primary metric scales without labels.

## Supporting metrics

Signal recall · evidence precision · answer-distribution accuracy · p50/p95 latency ·
calls, tokens and cost per case · compression ratio after dedup · abstention correctness.

## Case matrix — 12 cases minimum

1. Binary choice asked aloud, chat answers `left` / `right`
2. Numeric rating asked, chat replies with bare numbers
3. Gameplay failure triggers laughter
4. Character or name mention triggers a meme flood
5. Audio problem triggers technical warnings — **no supported cause in speech → `unknown`**
6. Teammate speech misattributed to the streamer (diarization failure — a known real one)
7. Frame event matters while speech is silent
8. Speech matters while the frame is uninformative
9. Two competing topics simultaneously
10. Heavy spam that must collapse without losing volume
11. Sarcasm creating ambiguity → confidence must drop
12. A window with **no signal** → the system must abstain
13. *(if time)* Prompt-injection text inside chat, treated as data not instruction
14. *(if time)* A reference depending on an earlier window (memory)

Cases 5, 11, 12 are where the product wins. Feature at least one in the video.

## Gold label format

```json
{
  "case_id": "c07",
  "fixture": "self_2026-08-29_2140",
  "window_ms": [1724951180000, 1724951240000],
  "gold_signals": [
    {"type": "audience_answer", "trigger_event_id": "tr_881",
     "relevant_message_ids": ["msg_9912", "msg_9915"],
     "distribution": {"left": 0.62, "right": 0.38}},
    {"type": "warning", "trigger_event_id": "unknown",
     "relevant_message_ids": ["msg_9940"]}
  ],
  "must_abstain": false
}
```

## Protocol — freeze before you run

1. Freeze case definitions, gold labels, matching rules and thresholds **before** the final run.
2. Baseline and final receive **identical** event windows and output schema.
3. `temperature=0` everywhere evaluated; record the model and provider per run.
4. Persist raw predictions, normalized predictions, scorer decisions and trace id for every case.
5. Publish complete results including failures — not only the wins.
6. Report runtime and cost per case.

## Fair baseline

One direct prompt receiving **the same raw events** the final system sees — chat, final
transcript segments, frame captions, ids, timestamps — with the same output schema and card cap.
No tools, no reduction, no rolling state, no provenance gate, no verifier, no memory.

A chat-only run is a **diagnostic ablation**, not the headline baseline. Comparing multimodal
against chat-only would measure the value of giving the system more data, not the value of the
agentic workflow — anyone reading carefully will spot that instantly.

```
chat-only ablation      -> why stream context is needed at all
single-prompt baseline  -> what a strong simple approach already achieves
final workflow          -> what tools, grouping and verification added
```
