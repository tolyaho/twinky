# Grouping arms — the labels, frozen before any arm ran

`pair_labels.json` assigns an intent to every message in two windows. Two messages are a
**positive pair** when they share an intent id.

## Why this exists

Compression is not a metric for grouping. A method that merges everything into one group
compresses perfectly and is useless. Pair-level precision and recall against fixed labels is a
metric, and it only means anything if the labels were fixed **first**.

## The freeze, and how to check it

These labels were written by reading the messages and nothing else — no arm was run, and the
embedding arm did not exist in the tree when they were committed. That is checkable rather than
claimed: this file and `pair_labels.sha256` land in a commit that contains **no arm code**, and
`test_pair_labels.py` fails if the labels change without the checksum changing with them.

```
sha256sum evals/grouping/pair_labels.json      # must match pair_labels.sha256
git log --oneline -- evals/grouping/           # the freeze commit
```

## What they are not

**Model-drafted and not human-reviewed** — `"reviewed": false`, exactly like `evals/gold`. I read
the messages and assigned the intents; a person has not confirmed them. Any number computed
against these labels inherits that caveat and must carry it.

## Conventions

| id | meaning |
|---|---|
| a named intent | a real cluster; every message sharing it is a positive pair |
| `x<n>` | a cluster of one. Never pairs with anything, including other `x` ids |
| `unsure` | excluded from scoring in both directions |

The `x<n>` convention matters. A single `other` bucket would make every unrelated singleton a
positive pair with every other, which inflates recall for any arm that over-merges — precisely
the failure mode being tested for.

## The windows, and why these two

| window | messages | shape |
|---|---:|---|
| `stableronaldo` w2 | 79 | a word-guessing game: two different puzzles in one minute, `ame…` then `dr…` |
| `yugi` w9 | 85 | topics, reactions and directed replies — no puzzle, much more varied |

They are the two shapes the arms disagree on. Prefix rules should win the first and may over-merge
the second; a token or embedding method should do the opposite.


---

## Measured — arms A and B

`python -m evals.grouping.score_arms`, free, deterministic, no keys.

| arm | precision | recall | F1 |
|---|---:|---:|---:|
| **A · exact canonical** | **1.000** | 0.057 | 0.107 |
| **B · token + prefix** (shipped) | 0.926 | **0.257** | **0.403** |

Arm B carries **4.5× the recall for a 7-point precision cost**, and F1 nearly quadruples. That is
the iteration-49 argument — exact matching splits one audience signal into dozens of rows of one —
restated as a number against labels that were fixed before either arm ran.

Both predictions written above, before the arms were run, held:

| window | A recall | B recall | B precision |
|---|---:|---:|---:|
| `stableronaldo` w2 — the word game | 0.032 | **0.230** | **1.000** |
| `yugi` w9 — varied | 0.204 | **0.418** | 0.745 |

The prefix rule wins the word-guessing window outright and gives up precision on the varied one,
which is exactly the trade it was predicted to make. Arm A cannot produce a false pair at all —
identical text really is the same thing — and that is why its precision is 1.000 and why its
recall is close to nothing.

**Every figure here inherits `reviewed: false`.** The labels are model-drafted. They are good
enough to separate two arms by a factor of four; they are not good enough to call a 2-point
difference.
