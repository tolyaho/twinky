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

---

## Measured — arm C, embeddings. Not adopted.

`text-embedding-3-small`, single-link agglomeration by cosine, one batched call per window,
recorded once and replayable with no key.

Arm C has a free parameter that A and B do not, so **the whole sweep is reported** rather than a
chosen point. Quoting only the best row would be quoting a number picked by looking at the
answers.

| threshold | precision | recall | F1 |
|---:|---:|---:|---:|
| 0.30 | 0.247 | 0.993 | 0.395 |
| **0.40** | 0.530 | 0.649 | **0.583** |
| 0.45 | 0.644 | 0.489 | 0.556 |
| 0.50 | 0.910 | 0.319 | 0.472 |
| 0.55 | 0.973 | 0.289 | 0.446 |
| 0.60 | 0.974 | 0.140 | 0.244 |
| 0.65 | 0.995 | 0.135 | 0.238 |
| 0.70 | 1.000 | 0.128 | 0.227 |
| 0.80 | 1.000 | 0.100 | 0.182 |

### The pooled best is an averaging artifact

C's headline F1 of **0.583 at 0.40** looks like it beats arm B's 0.403 outright. It does not.
Split by window, that single threshold produces:

| window | precision | recall | F1 |
|---|---:|---:|---:|
| `stableronaldo` w2 — the word game | **1.000** | 0.626 | **0.770** |
| `yugi` w9 — varied | **0.164** | 0.786 | 0.272 |

At 0.40 arm C is the best result anything has produced on the word-guessing window **and close to
worthless on the varied one** — precision 0.164 means five of every six pairs it proposes are
wrong. The pooled number averages a triumph with a failure and reports neither.

**The threshold does not transfer between windows**, and that is the same instability the team
recorded in October 2025 and March 2026 — *"it splits into 100 clusters, but they're all
different… with not-great accuracy"*. This reproduces it with a number attached. Why it happens is
visible in the data: word-game chat is near-duplicate short strings, so cosine separates cleanly;
varied chat is uniformly short and colloquial, so almost everything looks similar and one
threshold collapses the window.

### At a single transferable threshold, C is modestly ahead

| arm | precision | recall | F1 |
|---|---:|---:|---:|
| B · token + prefix (shipped) | 0.926 | 0.257 | 0.403 |
| C @0.50 | 0.910 | 0.319 | 0.472 |
| C @0.55 | **0.973** | **0.289** | 0.446 |

At comparable-or-better precision, C@0.55 beats B on both axes — a real gain, and a small one.

### Why it is not adopted

1. **The gain is small and the cost is categorical.** B is free, keyless and deterministic; the
   whole grouping path runs in Tier 0 live chat with no provider at all. C needs an API key at
   record time and a network round trip per window.
2. **The winning threshold was chosen by looking at the labels.** That is tuning on the test set.
   0.55 is defensible only because these labels exist, and they are model-drafted.
3. **It is one day before the deadline** and swapping the shipped grouping arm would move the
   board, the rail, the questions panel and the live counts all at once.

So: **measured, published, not adopted** — and, unusually, that is not because it lost. It is
because the metric it won on is not the one the product is bought on, and the parameter it won
with is not one that can be chosen honestly in advance.

**Every figure here inherits `reviewed: false`.** Two windows, 164 messages, model-drafted labels.
