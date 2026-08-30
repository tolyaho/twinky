"""Score grouping arms against the frozen pair labels.

Pair-level precision and recall, because compression is not a metric: an arm that merges every
message into one group compresses perfectly, scores 1.0 recall, and is useless. Precision is what
stops that, and the two together are what make "better grouping" a claim rather than a feeling.

The labels were frozen first, in a commit containing no arm code. Nothing here may edit them —
`test_pair_labels.py` checks the file against its checksum on every run.

    python -m evals.grouping.score_arms          # free, deterministic, no keys
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from ts.events import Event
from ts.ingest.replay import load_fixture
from ts.workflow.reduce import canonical, group_chat

LABELS = Path("evals/grouping/pair_labels.json")
FIXTURES = Path("evals/fixtures")


# ------------------------------------------------------------------------------ the arms
# Each arm answers one question: which messages belong together? It returns `{event_id: group}`,
# and a message absent from the mapping is a group of one.

def arm_exact(chat: Sequence[Event]) -> Dict[str, str]:
    """A — canonical equality, the rule the reducer shipped with."""
    return {e.event_id: canonical(e.text) or f"~{e.event_id}" for e in chat}


def arm_token_prefix(chat: Sequence[Event]) -> Dict[str, str]:
    """B — the shipped rules: reaction bucket, then 4-char prefix, then content token."""
    out: Dict[str, str] = {}
    for group in group_chat(chat):
        for event_id in group.event_ids:
            out[event_id] = group.key
    return out


ARMS: List[Tuple[str, Callable[[Sequence[Event]], Dict[str, str]]]] = [
    ("A · exact canonical", arm_exact),
    ("B · token + prefix", arm_token_prefix),
]


# ---------------------------------------------------------------------------- the metric

def score(chat: Sequence[Event], gold: Dict[str, str],
          predicted: Dict[str, str]) -> Dict[str, float]:
    """Pair precision, recall and F1 over every pair of scoreable messages.

    `unsure` messages are dropped in both directions before any pair is formed, so an arm is
    never rewarded or punished for a message the labeller could not call.
    """
    ids = [e.event_id for e in chat if gold.get(e.event_id) not in (None, "unsure")]
    tp = fp = fn = 0
    for a, b in combinations(ids, 2):
        same_gold = gold[a] == gold[b]
        # A message the arm never grouped is a group of one, and two groups of one are not a pair.
        ga, gb = predicted.get(a), predicted.get(b)
        same_pred = ga is not None and ga == gb
        if same_pred and same_gold:
            tp += 1
        elif same_pred:
            fp += 1
        elif same_gold:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"pairs": len(ids) * (len(ids) - 1) // 2, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def run(arms=ARMS) -> Dict[str, object]:
    doc = json.loads(LABELS.read_text(encoding="utf-8"))
    results: Dict[str, object] = {"reviewed": doc["reviewed"], "windows": []}
    totals: Dict[str, Dict[str, int]] = {name: {"tp": 0, "fp": 0, "fn": 0} for name, _ in arms}

    for window in doc["windows"]:
        index = load_fixture(FIXTURES / window["fixture"])
        start, end = window["window_ms"]
        chat = index.window(start, end, types=["chat_message"])
        gold = {l["id"]: l["intent"] for l in window["labels"]}

        row = {"window": f"{window['fixture']} w{window['window']}", "arms": {}}
        for name, arm in arms:
            s = score(chat, gold, arm(chat))
            row["arms"][name] = s
            for k in ("tp", "fp", "fn"):
                totals[name][k] += s[k]
        results["windows"].append(row)

    overall = {}
    for name, t in totals.items():
        p = t["tp"] / (t["tp"] + t["fp"]) if t["tp"] + t["fp"] else 0.0
        r = t["tp"] / (t["tp"] + t["fn"]) if t["tp"] + t["fn"] else 0.0
        overall[name] = {**t, "precision": round(p, 3), "recall": round(r, 3),
                         "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}
    results["overall"] = overall
    return results


def main() -> int:
    results = run()
    for window in results["windows"]:
        print(f"\n{window['window']}")
        for name, s in window["arms"].items():
            print(f"  {name:22s} P {s['precision']:.3f}  R {s['recall']:.3f}  "
                  f"F1 {s['f1']:.3f}   (tp {s['tp']}, fp {s['fp']}, fn {s['fn']})")
    print("\nboth windows pooled")
    for name, s in results["overall"].items():
        print(f"  {name:22s} P {s['precision']:.3f}  R {s['recall']:.3f}  F1 {s['f1']:.3f}")
    print("\nLabels are model-drafted and not human-reviewed "
          f"(reviewed={results['reviewed']}). Every number above inherits that.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
