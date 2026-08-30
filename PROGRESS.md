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

## 2026-08-30T00:41Z — iteration 4
Attempted: A4 — build the 12 eval cases against whatever fixtures exist.
Result: `make test` green, 94 -> 98. Built the cases the scaffold fixture honestly supports:
`c03_failure_laughter` and `c12_no_signal_abstain`, taking the frozen set 2 -> 4. Annotated all
four with `fixture_kind`; `make eval` now banners non-capture fixtures NOT A REPORTED RESULT and
prints each fixture's provenance. Case inventory with per-case blockers in `evals/DATA.md`.
Next: A5 — `report/debrief.py`, roll verified cards into the post-stream document.
Blockers: 8 of 12 cases need real captures (RISKS #12, downstream of #2). Case 11 (sarcasm) is
one of the three the product wins on and cannot be written without a real fixture.

## 2026-08-30T01:09Z — iteration 5
Attempted: A5 — `report/debrief.py`, roll verified cards into the post-stream document.
Result: `make test` green, 98 -> 113. `build()` + `render_markdown()` implemented, wired as
`ts.cli debrief` and `make debrief`; writes `<fixture>.debrief.md` and `.json`. Six sections, all
derived from verified cards with no model call. Rendered the artifact by hand and fixed what it
exposed: recurring themes were counting words out of model-written titles and returned "chat",
"says", "the" — now sourced from trigger quotes and answer distributions only.
Next: A6 — dashboard on real replay output; `DESIGN.md` is authoritative.
Blockers: none. RISKS #10 and #12 still open.
