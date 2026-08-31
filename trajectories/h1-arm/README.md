# Removed experiment #4 — the H1 arm's runs

Not the product. These are the trajectories of the arm described in
`docs/IMPROVEMENT_CHANGELOG.md` as **Removed experiment #4**: `Tools.group_repeated` pointed at
`group_chat` instead of `reduce_chat`. It was measured, it lost on both adopt criteria, and the
code was reverted — see `experiments/README.md`.

They live here rather than in `../product-agent/` because trace ids derive from
`(agent, case_id)` and are stable across runs, so writing them beside the shipped runs would
**overwrite** them in place with this arm's content. That happened once, was caught by the
agent-graph test, and is why every documented command for this arm sets `TS_TRACE_DIR`.

`evidence/h1/predictions.json` points at these files, so every card in that report can be traced
back to the conversation that produced it. Nothing in this directory is counted in the 118 runs
quoted in `README.md` and `SUBMISSION.md`, which are the shipped systems only.
