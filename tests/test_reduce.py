from pathlib import Path

from ts.events import Event
from ts.workflow.reduce import (EMPTY_KEY, EMPTY_SAMPLE, REACTION_KEY, canonical,
                               compression_ratio, group_chat, grouped_summary, is_reaction,
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


# --------------------------------------------------------------------------------- grouping
# Exact canonical equality is the wrong unit for an audience signal: twenty people guessing an
# on-screen word type twenty different strings, so the board drew twenty rows of one message
# each. These rules are the fix, and they are deterministic — no model, no cost, no key.


def _window(fixture, w):
    from ts.ingest.replay import load_fixture
    index = load_fixture(Path(__file__).resolve().parents[1] / "evals/fixtures" / fixture)
    start = index.start_ms + w * 60_000
    return index.window(start, start + 60_000, types=["chat_message"])


def test_rule_b_groups_single_word_guesses_by_prefix():
    groups = group_chat(_msgs("parade", "parallel", "parat", "parab"))

    assert [(g.label, g.count, g.rule) for g in groups] == [("para…", 4, "prefix")]


def test_a_prefix_below_the_floor_is_not_a_signal():
    """Three people typing similar words is noise. The threshold is what stops the board
    inventing a signal out of coincidence."""
    assert group_chat(_msgs("parade", "parallel", "parat")) == []


def test_rule_a_groups_sentences_by_a_shared_content_token():
    groups = group_chat(_msgs("is that violet", "VIOLET MY GOAT", "violet murders?"))

    assert [(g.label, g.count, g.rule) for g in groups] == [("violet", 3, "token")]


def test_a_prefix_bucket_folds_into_the_word_it_is_a_prefix_of():
    """Rule B runs first, so single-word `VIOLET` lands in `viol…` while the sentences land in
    `violet` — one signal, two rows, which is the bug this function exists to fix."""
    groups = group_chat(_msgs("VIOLET", "Violet", "violet", "VIOLET.",
                              "is that violet", "VIOLET MY GOAT", "violet murders?"))

    assert [(g.label, g.count) for g in groups] == [("violet", 7)]


def test_laughter_and_emote_only_messages_share_one_counted_bucket():
    """Left in their own rows they top every ranking, and 'the audience laughed' is volume,
    not a topic."""
    groups = group_chat(_msgs("LOL", "ахахаха", "hahaha", "😂😂😂", "KEKW", "xdddd"))

    assert [(g.key, g.count, g.rule) for g in groups] == [(REACTION_KEY, 6, "reaction")]


def test_a_sentence_containing_lol_is_not_laughter():
    assert is_reaction("lol") and not is_reaction("lol he actually did it")


def test_stopwords_and_short_tokens_never_carry_a_group():
    assert group_chat(_msgs("he is the one", "she is the one", "it is the one")) == []


def test_a_four_character_token_and_a_prefix_do_not_collide():
    """`jump` is reachable as a prefix bucket and as a content token. Sharing one dict key let
    whichever rule ran second relabel the other's group."""
    groups = group_chat(_msgs("JUMPP", "jump", "Jumpp", "JUMP",
                              "JUMP IN", "he should jump", "why not jump"))

    assert len(groups) == 1
    assert (groups[0].label, groups[0].count) == ("jump", 7)


def test_every_message_joins_at_most_one_group():
    messages = _msgs("violet myers", "is that violet", "violet on screen",
                     "myers is here", "myers again", "LOL", "😂")

    groups = group_chat(messages)
    ids = [eid for g in groups for eid in g.event_ids]

    assert len(ids) == len(set(ids))
    assert sum(g.count for g in groups) <= len(messages)


def test_grouping_is_deterministic():
    messages = _msgs("violet myers", "myers violet", "violet again", "myers again", "LOL")

    assert ([g.to_dict() for g in group_chat(messages)]
            == [g.to_dict() for g in group_chat(messages)])


def test_samples_are_verbatim_and_bounded():
    groups = group_chat(_msgs("VIOLET!!!", "Violet", "violet", "VIOLET.", "violet?"))

    assert groups[0].samples == ["VIOLET!!!", "Violet", "violet"]


def test_grouped_summary_accounts_for_every_message():
    """Six rows out of 1288 messages read as the whole window unless the footer says what
    happened to the other thousand."""
    messages = _msgs("parade", "parallel", "parat", "parab", "unrelated thing entirely")

    summary = grouped_summary(messages, group_chat(messages))

    assert summary == {"messages": 5, "groups": 1, "grouped": 4, "ungrouped": 1}


def test_the_measured_grouping_figures_reproduce():
    """The two numbers published in DECISIONS.md and PROGRESS.md, pinned to the fixtures they
    were measured on. If a rule changes, these move, and the documents have to move with them."""
    violet = [g for g in group_chat(_window("marlon_2026-08-30T0715", 6)) if g.label == "violet"]
    assert (violet[0].count, violet[0].rule) == (27, "token")

    para = [g for g in group_chat(_window("stableronaldo_2026-08-30T0723", 9))
            if g.label == "para…"]
    assert (para[0].count, para[0].rule) == (41, "prefix")


def test_grouping_does_not_disturb_the_recorded_reducer():
    """`reduce_chat` output is rendered into the agent's prompt and therefore hashed into every
    recorded model call. Grouping is additive precisely so keyless replay keeps hitting."""
    chat = _window("stableronaldo_2026-08-30T0723", 9)

    assert len(reduce_chat(chat)) == 76
    assert sum(b.count for b in reduce_chat(chat)) == len(chat)
