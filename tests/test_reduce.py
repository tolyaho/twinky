from pathlib import Path

from ts.events import Event
from ts.workflow.reduce import (EMPTY_KEY, EMPTY_SAMPLE, canonical, compression_ratio,
                               reduce_chat)


def chat(i, text, ts):
    return Event(f"m{i}", "chat_message", ts, {"text": text, "author": f"u{i}"})


def test_canonical_collapses_laughter_variants():
    assert canonical("АХАХАХАХА") == canonical("ахахаха") == canonical("Ахахахаха!!!")


def test_canonical_collapses_repeated_tokens():
    assert canonical("LUL LUL LUL") == canonical("LUL")


def test_canonical_ignores_punctuation_and_case():
    assert canonical("left!!!") == canonical("LEFT") == "left"


def test_reduce_groups_and_keeps_counts_and_ids():
    evs = [chat(1, "лес", 100), chat(2, "ЛЕС", 200), chat(3, "лес!!", 300), chat(4, "база", 400)]
    bursts = {b.key: b for b in reduce_chat(evs)}
    assert bursts["лес"].count == 3
    assert bursts["лес"].event_ids == ["m1", "m2", "m3"]
    assert bursts["лес"].first_ts_ms == 100 and bursts["лес"].last_ts_ms == 300
    assert bursts["база"].count == 1


def test_reduce_is_deterministic():
    evs = [chat(i, t, i * 10) for i, t in enumerate(["a", "b", "a", "c", "b", "a"])]
    assert [b.key for b in reduce_chat(evs)] == [b.key for b in reduce_chat(evs)] == ["a", "b", "c"]


def test_keep_ids_is_bounded():
    evs = [chat(i, "LUL", i * 10) for i in range(50)]
    assert len(reduce_chat(evs, keep_ids=5)[0].event_ids) == 5
    assert reduce_chat(evs, keep_ids=5)[0].count == 50


def test_reduce_ignores_non_chat():
    evs = [chat(1, "лес", 100), Event("t1", "transcript_segment", 50, {"text": "куда идти"})]
    assert len(reduce_chat(evs)) == 1


def test_compression_ratio():
    evs = [chat(i, "LUL", i * 10) for i in range(10)]
    assert compression_ratio(evs, reduce_chat(evs)) == 0.1


# --------------------------------------------------------------------------- emotes and volume
# The reducer claims to preserve counts. It did not: `[^\w\s]+` deleted every symbol, so an
# emote-only message canonicalised to nothing and was dropped — on Twitch, the most common
# reaction there is.
def _msgs(*texts):
    return [Event(f"m{i}", "chat_message", 1000 + i, {"text": t})
            for i, t in enumerate(texts)]


def test_an_emote_only_message_survives():
    assert canonical("😂😂😂") != ""
    assert canonical("🎉") == "🎉"


def test_an_emote_run_collapses_like_any_other_run():
    assert canonical("😂😂😂😂😂") == canonical("😂😂")


def test_an_emoji_is_not_stripped_out_of_mixed_text():
    assert canonical("😂 lol") == "😂 lol"


def test_punctuation_still_collapses_away():
    assert canonical("!!!") == ""
    assert canonical("лес!!") == "лес"


def test_a_punctuation_only_message_is_counted_not_dropped():
    bursts = reduce_chat(_msgs("!!!", "???", "лес"))

    empty = [b for b in bursts if b.key == EMPTY_KEY]
    assert len(empty) == 1 and empty[0].count == 2
    assert empty[0].sample == EMPTY_SAMPLE


def test_burst_counts_always_sum_to_the_messages_in_the_window():
    """The invariant the module claims. Anything dropped here is volume the agent never sees
    and a distribution that quietly under-counts."""
    messages = _msgs("😂😂😂", "😂😂", "!!!", "лес", "ЛЕС", "база", "🎉", "?!")

    bursts = reduce_chat(messages)

    assert sum(b.count for b in bursts) == len(messages)


def test_the_sample_fixture_reduces_exactly_as_before():
    """The emote fix must not move anything already frozen. It does not: the scaffold fixture
    has no emoji, so its bursts, counts and ratio are unchanged."""
    from ts.ingest.replay import load_fixture

    index = load_fixture(Path(__file__).resolve().parents[1] / "evals/fixtures/sample")
    chat = [e for e in index if e.type == "chat_message"]

    bursts = reduce_chat(chat)

    assert len(bursts) == 15
    assert sorted((b.count for b in bursts), reverse=True)[:4] == [9, 5, 4, 3]
    assert round(compression_ratio(chat, bursts), 3) == 0.469
