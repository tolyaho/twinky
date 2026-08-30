"""Arm C — embedding clustering, measured and not adopted.

The team ran this twice and recorded ~100 unstable clusters both times. It is here as an arm, not
as a fix, and these tests hold the measurement honest: the cache must make it replayable for
nothing, the clustering must be deterministic, and the threshold sweep must stay in the record so
nobody can quietly quote the best number as if it had been chosen in advance.
"""
from pathlib import Path

import pytest

from evals.grouping.arm_embeddings import THRESHOLDS, arm, cluster
from evals.grouping.score_arms import ARMS, run
from ts.cache import CacheMiss, ResponseCache
from ts.events import Event

ROOT = Path(__file__).resolve().parents[1]


def chat(i, text):
    return Event(f"m{i}", "chat_message", 1_000 + i, {"text": text, "author": f"u{i}"})


def test_clustering_is_deterministic_and_transitive():
    messages = [chat(0, "a"), chat(1, "b"), chat(2, "c")]
    vectors = [[1.0, 0.0], [0.99, 0.14], [0.0, 1.0]]

    first = cluster(messages, vectors, 0.9)

    assert first == cluster(messages, vectors, 0.9)
    assert first["m0"] == first["m1"] != first["m2"]


def test_a_high_threshold_separates_and_a_low_one_merges():
    messages = [chat(0, "a"), chat(1, "b")]
    vectors = [[1.0, 0.0], [0.0, 1.0]]

    assert len(set(cluster(messages, vectors, 0.5).values())) == 2
    assert len(set(cluster(messages, vectors, -1.0).values())) == 1


def test_a_replay_miss_raises_rather_than_scoring_zero():
    """Unlike a cosmetic label, a missing embedding means the arm cannot be scored at all.
    Silently returning nothing would publish a zero that looks like a measurement."""
    with pytest.raises(CacheMiss):
        arm(0.5, ResponseCache(mode="replay"))([chat(0, "never embedded, not in the cache")])


def test_the_recorded_windows_replay_with_no_key(monkeypatch):
    for key in ("OPENAI_API_KEY", "TS_LLM_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    cache = ResponseCache(mode="replay")
    results = run(list(ARMS) + [("C @0.55", arm(0.55, cache))])

    assert results["overall"]["C @0.55"]["precision"] > 0


def test_the_threshold_does_not_transfer_between_windows(monkeypatch):
    """The finding. At 0.40 arm C is the best result anyone has produced on the word-guessing
    window and close to worthless on the varied one — which is the instability the team recorded
    twice, reproduced with a number on it."""
    for key in ("OPENAI_API_KEY", "TS_LLM_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    cache = ResponseCache(mode="replay")
    results = run(list(ARMS) + [("C @0.40", arm(0.40, cache))])
    word_game = next(w for w in results["windows"] if "stableronaldo" in w["window"])
    varied = next(w for w in results["windows"] if "yugi" in w["window"])

    assert word_game["arms"]["C @0.40"]["f1"] > 0.7
    assert varied["arms"]["C @0.40"]["precision"] < 0.3
    assert varied["arms"]["C @0.40"]["precision"] < varied["arms"]["B · token + prefix"]["precision"]


def test_the_whole_sweep_is_kept_not_just_the_best_point():
    """C has a free parameter that A and B do not. Reporting one threshold would be quoting a
    number chosen by looking at the answers."""
    assert len(THRESHOLDS) >= 8
    readme = (ROOT / "evals/grouping/README.md").read_text(encoding="utf-8")

    for t in (0.30, 0.40, 0.55, 0.80):
        assert f"{t:.2f}" in readme, f"threshold {t} is missing from the write-up"
    assert "tuning on the test set" in readme


def test_the_shipped_grouping_is_still_the_free_one():
    """Measured and not adopted. `reduce.py` must not have grown a dependency on embeddings."""
    source = (ROOT / "src/ts/workflow/reduce.py").read_text(encoding="utf-8")
    board = (ROOT / "src/ts/report/board.py").read_text(encoding="utf-8")

    for module in (source, board):
        assert "embedding" not in module.lower()
        assert "arm_embeddings" not in module
