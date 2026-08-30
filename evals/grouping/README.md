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
