# Progress log

Append-only. One block per working session. Never delete history.

Format:

```
## <iso timestamp> — iteration N
Attempted:
Result:
Next:
Blockers:
```

---

## 2026-08-29 — iteration 0
Attempted: scaffold created; determinism spine, cache, provenance validator and eval skeleton
written; unit tests passing offline.
Result: `make test` green. No fixtures yet, no measurements yet.
Next: P0-3 — record 3 fixtures while streams are live.
Blockers: none.

## 2026-08-29T20:24Z — iteration 1
Attempted: A1 — `ingest/enrich.py` Deepgram + vision paths through `ts.cache`, fake-provider tests.
Result: `make test` green, 59 -> 70. New `providers/deepgram.py`, `providers/vision.py`,
`tests/test_enrich.py`. Enrichment now records once and replays byte-identically with the
provider unplugged (asserted). `COST_LEDGER.md` opened at 0.00; no paid calls made.
Next: A2 — wire `ts/cli.py` `replay`, `baseline` and `serve` to the real implementations.
Blockers: none. A1 is code-complete but unexercised on real media — no fixture exists yet (P0-3).

## 2026-08-29T20:47Z — iteration 2
Attempted: A2 — wire `ts/cli.py` `replay`, `baseline` and `serve` to the real implementations.
Result: `make test` green, 70 -> 84. All three commands are real: tiled 60 s windows shared by
both systems, result document per system in `--out`, `CacheMiss` exits 3 without a paid call,
`serve` serves recorded output plus a labelled non-dashboard placeholder (`report/serve.py`).
Fixed a determinism defect found on the way: `trace_id` came from `uuid4`, so two replays of one
fixture produced different published documents. Now derived from `(agent, case_id)`.
Next: RISKS #10 — `python -m ts.cli` fails from a fresh clone without `PYTHONPATH=src`. P0, blocks C2.
Blockers: none for A2. Cache is still empty, so `make replay` exits 3 by design until B1.

## 2026-08-30T00:12Z — iteration 3
Attempted: A3 — wire baseline and agent into `evals/run_eval.py`, verify with fake providers.
Result: `make test` green, 84 -> 94. Both systems run over the identical window per frozen case
and are scored on EVERY emitted card, not just gate survivors — scoring survivors only would
force unsupported-rate to 0 for both and make the headline metric vacuous. Adds
`evidence/predictions.json` (protocol item 4) and an opt-in `--ablation`. `make eval` on an
empty cache exits 3 with no paid call (verified by hand).
Next: A4 — build the remaining 10 eval cases against the sample fixture; cases 5, 11, 12 first.
Blockers: none. RISKS #10 still open (`python -m ts.cli` needs `PYTHONPATH=src`), P0 for gate C2.
