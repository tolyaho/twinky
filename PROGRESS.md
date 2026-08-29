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
