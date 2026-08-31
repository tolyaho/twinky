# Prepared experiments — diagnosed, patched, not yet measured

Nothing in this directory is part of the product, the eval or `make test`. It holds work that was
diagnosed from the data and prepared to the point of being one command away from a number, but
that could not be measured in the time available because measuring it costs money and requires a
key.

**A prepared experiment is not a result.** Nothing here is quoted in `README.md`,
`SUBMISSION.md` or the changelog as an outcome, and the patches are not applied to the tree. The
three experiments that *were* measured — louder audio, the grounded arm, embedding clustering —
live in `docs/IMPROVEMENT_CHANGELOG.md` with their numbers, and two of them lost.

## `h1-group-chat.patch` — the agent's only view of chat is the old reducer

`Tools.group_repeated` — the agent's single window onto what the audience is saying — calls
`reduce_chat`, which groups by exact canonical form. The improved `group_chat` (reaction wave,
prefix rule, token rule) that the board has rendered since the grouping work landed was never
wired into the agent's tools.

So on the same window, at the same moment:

| what the agent is handed | what the board draws beside it |
|---|---|
| `?` × 42 · `LOL` × 28 · `??` × 14 | `violet` × 27 · `para…` × 38 · `drac…` × 56 |

The agent is asked what the room is reacting to while looking at punctuation counts.

**Measured, free, deterministic** — serialized tool output over the eleven frozen windows:

| reducer | characters | rows |
|---|---:|---|
| `reduce_chat` (what ships) | 197,952 | 19–174 per window, mostly count 1 |
| `group_chat` (this patch) | **51,358** | 2–20 per window |

It is 0.26× the size, which removes the obvious objection before it is raised: this is not a
bigger prompt, it is a quarter of one. Exact canonical form makes a row per distinct string, so a
174-message window became 174 near-empty rows.

**What is NOT known: whether it improves any published metric.** The prompt is the cache key, so
the agent arm has to be re-recorded before a single number moves, and that costs money. Until
that run happens this is a diagnosis, not an improvement.

### Running it

```bash
git apply experiments/h1-group-chat.patch
python scripts/record_h1.py                     # needs TS_LLM_API_KEY; ~$0.01, 11 cases
```

The script records into a temporary evidence and trajectory directory, prints the before/after
comparison against the adopt criteria, and never writes to `evidence/`. Adopting is a separate,
deliberate step.

**Adopt only if trigger accuracy ≥ 0.500 AND abstentions stay above zero.** An arm that grounds
more but stops abstaining is Removed experiment #2 shipped again under a new name. If it loses,
`git checkout -- src/ts/workflow/ cache/llm/` puts the frozen numbers straight back, and the
result gets written up as a removed experiment — a diagnosed failure that was measured is worth
recording; a broken comparison is not.

### Why the baseline is safe

`record` mode reads the cache before it calls a provider, and this patch touches only
`Tools.group_repeated` and `TOOLS_DOC` — which the baseline does not import; it takes `INTRO` and
`CARD_CONTRACT`. Verified rather than assumed: baseline + ablation over all eleven cases in
replay give **22 hits, 0 misses**, so their requests are unchanged and cannot be re-called.
`scripts/record_h1.py` re-runs that check and refuses to start if it ever stops being true.
