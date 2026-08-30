"""The pair-level labels, and the freeze that makes them worth anything.

Compression is not a metric for grouping — merging everything scores perfectly and is useless.
Pair precision and recall against fixed labels is a metric, and only if the labels were fixed
first. This file exists to make "first" checkable instead of claimed.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "evals/grouping/pair_labels.json"
DIGEST = ROOT / "evals/grouping/pair_labels.sha256"


def _doc():
    return json.loads(LABELS.read_text(encoding="utf-8"))


def test_the_labels_match_their_checksum():
    """Editing the labels after seeing an arm's score is the one move that would make every
    number computed from them meaningless. The checksum makes that edit loud."""
    body = LABELS.read_text(encoding="utf-8")

    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == DIGEST.read_text().strip(), \
        "the labels changed without the checksum — re-freeze deliberately or revert"


def test_they_are_declared_model_drafted_and_unreviewed():
    """Same standing as `evals/gold`. Claiming a human review that did not happen would be the
    one unrecoverable mistake in an evaluation."""
    doc = _doc()

    assert doc["reviewed"] is False
    assert "MODEL-DRAFTED, NOT HUMAN-REVIEWED" in doc["provenance"]


def test_every_message_in_the_window_carries_a_label():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from ts.ingest.replay import load_fixture
    from ts.report.board import windows

    for window in _doc()["windows"]:
        index = load_fixture(ROOT / "evals/fixtures" / window["fixture"])
        start, end = windows(index)[window["window"]]
        chat = index.window(start, end, types=["chat_message"])

        assert [start, end] == window["window_ms"]
        assert len(window["labels"]) == len(chat) == window["messages"]
        assert [c.event_id for c in chat] == [l["id"] for l in window["labels"]], \
            "the labels are no longer aligned to the messages they describe"


def test_singletons_never_pair_with_each_other():
    """A single `other` bucket would make every unrelated singleton a positive pair with every
    other, inflating recall for exactly the over-merging this is meant to detect."""
    for window in _doc()["windows"]:
        singles = [l["intent"] for l in window["labels"] if l["intent"].startswith("x")]

        assert len(singles) == len(set(singles)), "two messages share a singleton id"
        assert "other" not in {l["intent"] for l in window["labels"]}


def test_unsure_is_used_sparingly_and_is_excluded_by_the_rule():
    doc = _doc()

    assert "excluded from scoring in both directions" in doc["rule"]
    for window in doc["windows"]:
        unsure = sum(1 for l in window["labels"] if l["intent"] == "unsure")
        assert unsure / window["messages"] < 0.10, "too much was set aside to mean anything"


def test_both_window_shapes_are_represented():
    """Prefix rules should win the word-guessing window and may over-merge the varied one. One
    window would let an arm look good by being right about a single shape."""
    doc = _doc()
    shapes = {w["fixture"].split("_")[0] for w in doc["windows"]}

    assert shapes == {"stableronaldo", "yugi"}
    for window in doc["windows"]:
        named = Counter(l["intent"] for l in window["labels"]
                        if not l["intent"].startswith("x") and l["intent"] != "unsure")
        assert len(named) >= 2, "a window with one intent cannot separate the arms"
