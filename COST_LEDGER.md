# Cost ledger

Every paid run appends exactly one line. Never leave a paid run unlogged.

Format:

```
<iso> | <what> | calls=N | in_tok=N | out_tok=N | est_usd=N.NN | running_total=N.NN
```

Hard cap **$5.00**. At **$2.00** a warning goes at the top of `PROGRESS.md`. Estimate from the
provider's published price when a response carries no usage block.

`make test`, `make replay`, `make baseline` and `make eval` are free by construction: they run in
`TS_LLM_MODE=replay`, where a cache miss is a hard error rather than a silent API call.

---

2026-08-29T20:24Z | ledger opened, no paid calls yet | calls=0 | in_tok=0 | out_tok=0 | est_usd=0.00 | running_total=0.00
2026-08-30T08:20Z | enrich x4 fixtures (36 min audio, 72 frames); vision prompt fixed and 4 captions re-recorded | calls=~80 | est_usd=0.28 | running_total=0.30
2026-08-30T12:55Z | eval: discarded first run (44 calls) + repaired re-record with --ablation (48 calls) + 2 smoke runs, all gpt-4.1-nano | calls=94 | in_tok=528500 | out_tok=14134 | est_usd=0.06 | running_total=0.36
2026-08-30T14:10Z | tiled replay+baseline recorded for yugi and stableronaldo so make replay/baseline/debrief/demo run from cache | calls=79 | est_usd=0.03 | running_total=0.39
2026-08-30T20:05Z | tiled replay+baseline recorded for marlon_0715, to test whether the agent grounds any card on a third fixture (it does not) | calls=~30 | est_usd=0.02 | running_total=0.41
2026-08-31T00:40Z | live mode end-to-end: one 60s window captured from a live broadcast, enriched and analysed (Deepgram + vision + agent). Recorded to a temporary cache, so the committed reproduction cache is unchanged | calls=~6 | est_usd=0.01 | running_total=0.42
2026-08-30T17:40Z | NOTE: this line is EARLIER than the two above it. Those were stamped from an assumed date rather than the clock; this one is `date -u` at the moment of the run. The repo already records that its git history was reconstructed with assigned dates, and the same assumption leaked into two ledger lines and into the PROGRESS.md headings. Spend figures are unaffected — they are computed from token counts in the cache entries, not from timestamps | calls=0 | est_usd=0.00 | running_total=0.42
2026-08-30T17:40Z | grounded arm recorded: 1 case first to price it, then all 11 (--ablation --grounded). Existing agent/baseline/ablation entries were cache HITS and cost nothing; only the new arm was paid for. Result: the arm lost and was not adopted | calls=22 | in_tok=107546 | out_tok=3589 | est_usd=0.0122 | running_total=0.43
2026-08-30T18:47Z | group labels recorded for the three fixtures the shot list films (37 windows). First attempt batched per ROW — 45 calls on one fixture — and was discarded and re-recorded per WINDOW as FEATURES_V2 §2 specifies; the 45 orphaned entries were deleted, but the $0.0017 they cost is real and is included below | calls=79 | in_tok=22565 | out_tok=5123 | est_usd=0.0043 | running_total=0.43
2026-08-30T19:13Z | arm C embeddings: one batched text-embedding-3-small call per window over the two frozen label windows. Measured and NOT adopted | calls=2 | in_tok=723 | out_tok=0 | est_usd=0.0000 | running_total=0.43
2026-08-31T07:56Z | item H1 prepared and NOT recorded: the paid step was blocked by the sandbox and the change was reverted to keep the tree green. The free half was done — 22 replay hits proving baseline and ablation are untouched, and the serialized-size comparison over the eleven frozen windows | calls=0 | est_usd=0.00 | running_total=0.43
