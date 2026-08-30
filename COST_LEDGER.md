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
