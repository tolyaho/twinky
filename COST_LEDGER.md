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
