"""The pair-level scorer for grouping arms.

The metric exists because compression is not one: an arm that merges everything scores perfect
recall and is useless. Most of these tests are about the degenerate cases, because a metric that
cannot catch them is not a metric.
"""
from pathlib import Path

from evals.grouping.score_arms import arm_exact, arm_token_prefix, run, score
from ts.events import Event

ROOT = Path(__file__).resolve().parents[1]


def chat(i, text, ts=0):
    return Event(f"m{i}", "chat_message", ts + i, {"text": text, "author": f"u{i}"})


MESSAGES = [chat(0, "violet"), chat(1, "violet"), chat(2, "wtf"), chat(3, "wtf")]
GOLD = {"m0": "a", "m1": "a", "m2": "b", "m3": "b"}


def test_a_perfect_arm_scores_one():
    perfect = {"m0": "g1", "m1": "g1", "m2": "g2", "m3": "g2"}

    assert score(MESSAGES, GOLD, perfect)["f1"] == 1.0


def test_merging_everything_is_caught_by_precision():
    """The whole reason compression is not the metric. This arm scores perfect recall."""
    everything = {m.event_id: "one_big_group" for m in MESSAGES}

    result = score(MESSAGES, GOLD, everything)

    assert result["recall"] == 1.0
    assert result["precision"] < 0.6, "over-merging must cost precision"


def test_splitting_everything_is_caught_by_recall():
    nothing = {m.event_id: f"only_{m.event_id}" for m in MESSAGES}

    result = score(MESSAGES, GOLD, nothing)

    assert result["recall"] == 0.0
    assert result["precision"] == 0.0, "no pairs proposed is not perfect precision"


def test_a_message_the_arm_never_grouped_pairs_with_nothing():
    """Absent from the mapping means a group of one. Two groups of one are not a pair, and
    treating `None == None` as agreement would score silence as a correct answer."""
    partial = {"m0": "g1", "m1": "g1"}

    result = score(MESSAGES, GOLD, partial)

    assert result["tp"] == 1 and result["fp"] == 0
    assert result["fn"] == 1, "the wtf pair was missed, not ignored"


def test_unsure_messages_are_excluded_from_both_directions():
    """An arm is never rewarded or punished for a message the labeller could not call."""
    gold = {**GOLD, "m3": "unsure"}
    arm = {"m0": "g", "m1": "g", "m2": "g", "m3": "g"}

    result = score(MESSAGES, gold, arm)

    assert result["pairs"] == 3, "m3 should not appear in any pair"
    assert result["fp"] == 2, "m2 wrongly joined m0 and m1, and that still counts"


# ------------------------------------------------------------------ against the real labels

def test_the_shipped_arm_beats_the_one_it_replaced():
    """Iteration 49 replaced exact-match grouping on the argument that it split one signal into
    many. This is that argument as a number, against labels frozen before either arm was run."""
    results = run()
    a = results["overall"]["A · exact canonical"]
    b = results["overall"]["B · token + prefix"]

    assert b["recall"] > a["recall"] * 4, "arm B was supposed to be the whole point"
    assert b["f1"] > a["f1"]
    assert a["precision"] == 1.0, "exact equality cannot produce a false pair"


def test_the_prefix_arm_wins_the_word_game_window_and_pays_on_the_varied_one():
    """Both predictions were written into `evals/grouping/README.md` before the arms were run."""
    results = run()
    word_game = next(w for w in results["windows"] if "stableronaldo" in w["window"])
    varied = next(w for w in results["windows"] if "yugi" in w["window"])

    assert word_game["arms"]["B · token + prefix"]["precision"] == 1.0
    assert varied["arms"]["B · token + prefix"]["precision"] < 1.0, "over-merging, as predicted"


def test_the_result_carries_the_unreviewed_caveat():
    assert run()["reviewed"] is False


def test_scoring_needs_no_key_and_no_network():
    source = (ROOT / "evals/grouping/score_arms.py").read_text(encoding="utf-8")

    for forbidden in ["ResponseCache", "httpx", "requests", "API_KEY"]:
        assert forbidden not in source
