# Experiments held outside the product

Nothing here is imported by `src/`, run by `make test`, or applied to the tree. It holds a change
that was built, recorded, measured and then declined, kept in a form that still runs.

## `h1-group-chat.patch` — the agent's chat tool, pointed at the shipped grouper

**Measured, and it lost.** The full write-up with both tables is Removed experiment #4 in
`docs/IMPROVEMENT_CHANGELOG.md`; the short version:

| metric | shipped (`reduce_chat`) | H1 (`group_chat`) |
|---|---:|---:|
| trigger accuracy | **0.500** | **0.000** |
| unsupported-card rate | 0.739 | **1.000** |
| signal recall | 0.182 | 0.182 |
| abstentions | 1 | **0** |
| `E_CIRCULAR_EVIDENCE` | 8 | **25** |

The diagnosis was right — `Tools.group_repeated` really did call the old exact-match reducer, so
the agent read `?` × 42 while the board showed `violet × 27` beside it — and the patch really does
give it the good groups in **0.26×** the characters. It made the agent worse anyway: handed a
group it could describe, it wrote a confident card and named a message *from that group* as the
cause of that same group. Every abstention, every honest `unknown` and all four real speech
triggers went to zero.

The adopt rule was fixed before the run: trigger accuracy ≥ 0.500 **and** abstentions above zero.
H1 fails both, so the code was reverted and only the recording kept.

### Reproducing the loss, with no key

The 24 recorded responses are committed, so this needs no credential and costs nothing:

```bash
git apply experiments/h1-group-chat.patch
TS_LLM_MODE=replay TS_TRACE_DIR=/tmp/h1-traj \
  python -m evals.run_eval --ablation --out /tmp/h1     # 46 hits, 0 misses
git apply -R experiments/h1-group-chat.patch
```

**`TS_TRACE_DIR` is not optional.** Trace ids derive from `(agent, case_id)` and are therefore
stable across runs, so a replay without it rewrites ten files in `trajectories/product-agent/` —
a committed deliverable — with this arm's content. That happened once here and was caught by the
agent-graph test; the redirect is why the command above is safe to paste.

### Re-recording it from scratch

`scripts/record_h1.py` does the whole thing in one command and needs a key. It records the agent
arm only, into temporary evidence and trajectory directories, refuses to start unless baseline and
ablation still produce 22 replay hits and 0 misses, takes only the key and base URL from `.env`
(never the model names — that file sets `TS_TEXT_MODEL` twice), and prints both tables against the
adopt criteria. Cost when it was run: **$0.0064**, 24 calls.

### Why the frozen comparison was never at risk

`record` mode reads the cache before it calls a provider, and the patch touches only
`Tools.group_repeated` and `TOOLS_DOC` — which the baseline does not import; it takes `INTRO` and
`CARD_CONTRACT`. Checked before the run (22 hits, 0 misses) and confirmed after: baseline and
`ablation_chat_only` reproduced their published trigger accuracies, 0.000 and 1.000, exactly.
