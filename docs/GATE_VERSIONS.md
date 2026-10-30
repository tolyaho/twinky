# Provenance gate versions and immutable evidence

A gate checks citations and time, not semantic causality. Its definition is part of a reported
metric. Changing that definition must not silently revise an old result.

| name | circular evidence rule | artifacts |
|---|---|---|
| `strict-v1` | trigger cannot also be cited evidence | historical H1 results, `evidence/h1/` and `trajectories/h1-arm/` |
| `reaction-v2` (current) | a reaction can cite its earlier chat trigger plus strictly later chat evidence | canonical `evidence/summary.json`; current viewer projection |

Both versions retain the same remaining ID, time, quote-overlap and abstention checks. The
version parameter is explicit in `check_card` and `apply_gate`; unknown versions fail loudly.
Legacy `verified` means checks passed, not that a causal hypothesis is true. Missing quotes and
`unknown` triggers can pass. Trigger kind, title semantics and distributions are not validated.

## H1: one set of predictions, two measurement definitions

H1 changed the prompt's tool description and `group_repeated` implementation to the broader
`group_chat`. `experiments/h1-group-chat.patch` is preserved as the historical proposal;
`evals.h1` now runs that same arm without editing tracked source files.

| H1 agent result | strict-v1 historical | reaction-v2 rescore |
|---|---:|---:|
| emitted cards | 25 | 25 |
| rejected cards / unsupported rate | 25 / 1.000 | 5 / 0.200 |
| trigger accuracy | 0.000 | 0.000 |
| gold recall | 2/11 | 2/11 |

All 25 raw cards agree after removing derived status/gate/action fields. Twenty gate decisions
change solely because of the reaction exception. This is not an improved model, a new recording,
or evidence of semantic correctness. H1 still fails the original trigger-accuracy adoption rule.
The versioned summary in [GATE_RESCORE.json](GATE_RESCORE.json) references source hashes and
records counts without duplicating viewer text or changing old evidence.

```bash
TS_LLM_MODE=replay .venv/bin/python -m evals.h1 --cases all --ablation --out .runtime/h1-reaction-v2
```

Expected: 46 cache hits, zero misses/provider calls. The historical 1.000 is not the expected
current-gate rerun. `tests/test_reproducibility_fixes.py` actually runs the H1 agent from cache
and compares its raw predictions, then evaluates both gates. The old summary-only assertion is
labelled as a historical artifact test.

## Traces and viewer

`Trace.write` is immutable on conflict. A replay cannot erase a real recorded `at_ms` or duration;
a changed trace gets a deterministic content-addressed path under ignored `.runtime/traces/`.
An identical existing trace is reused without writing. New default replay traces also stay in
`.runtime/`. Record-mode traces retain their measured timing; replay timing is null.

`report/results.py` projects frozen raw cards through `reaction-v2` in memory. `/api/replay`,
replay SSE, hero and debrief use this common loader. The projection records the source SHA-256
and current gate version. Agent cards passing the viewer's additional concrete-trigger/quote
filter total 5 + 5 + 3 over the three dashboard fixtures. They remain hypotheses.

Replay questions use an `as_of_ms` cutoff, including transcript segment end time. A later answer
cannot appear at an earlier window close. Historical files are preserved, not regenerated in place.
Changed CLI/evaluation output directed at an existing frozen artifact is refused; use `.runtime/`.
