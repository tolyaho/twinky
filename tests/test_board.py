"""The board and the rail.

Everything asserted here is computed from a committed fixture with no key, no network and no
model call, which is the point: Tier 0 of the live mode is exactly this code, so it has to hold
up where no paid provider is reachable at all.
"""
from pathlib import Path

from ts.events import Event, EventIndex
from ts.ingest.replay import load_fixture
from ts.report.board import board, is_question, questions, rail, windows

FIXTURES = Path(__file__).resolve().parents[1] / "evals/fixtures"


def chat(i, text, ts, author=None):
    return Event(f"m{i}", "chat_message", ts, {"text": text, "author": author or f"u{i}"})


def speech(i, text, ts):
    return Event(f"s{i}", "transcript_segment", ts, {"text": text})


def frame(i, text, ts):
    return Event(f"f{i}", "frame_caption", ts, {"text": text})


def _index(*events):
    return EventIndex(events)


def _window(fixture, w):
    index = load_fixture(FIXTURES / fixture)
    start, end = windows(index)[w]
    return index, start, end


# ------------------------------------------------------------------------------- attribution

def test_a_trigger_naming_the_word_chat_is_typing_is_a_matched_link():
    index = _index(frame(1, "the partial word para_ is visible", 1_000),
                   *[chat(i, t, 2_000 + i) for i, t in
                     enumerate(["parade", "parallel", "parat", "parab"])])

    row = board(index, 0, 60_000)["rows"][0]

    assert row["trigger"]["link"] == "matched"
    assert row["trigger"]["kind"] == "screen"


def test_merely_being_the_last_thing_on_screen_is_only_a_preceding_link():
    """Nearest-preceding attached 41 people brute-forcing a word puzzle to a caption about
    three people sleeping. A row header reads as causal however it is captioned, so the two
    strengths are distinguished rather than smoothed over."""
    index = _index(frame(1, "three people sleeping in a dimly lit room", 1_000),
                   *[chat(i, t, 2_000 + i) for i, t in
                     enumerate(["parade", "parallel", "parat", "parab"])])

    row = board(index, 0, 60_000)["rows"][0]

    assert row["trigger"]["link"] == "preceding"


def test_a_matched_row_outranks_a_bigger_preceding_one():
    index = _index(
        frame(1, "the partial word para_ is visible", 1_000),
        *[chat(i, t, 2_000 + i) for i, t in enumerate(["parade", "parallel", "parat", "parab"])],
        frame(2, "a dimly lit room", 10_000),
        *[chat(20 + i, t, 11_000 + i) for i, t in
          enumerate(["helix", "helicopter", "helium", "helipad", "helios", "helical"])])

    rows = board(index, 0, 60_000)["rows"]

    assert [r["trigger"]["link"] for r in rows] == ["matched", "preceding"]
    assert rows[0]["count"] < rows[1]["count"]


def test_a_wave_with_nothing_before_it_is_unattributed_not_invented():
    index = _index(*[chat(i, t, 2_000 + i) for i, t in
                     enumerate(["parade", "parallel", "parat", "parab"])])

    result = board(index, 0, 60_000)

    assert result["rows"] == []
    assert [g["label"] for g in result["unattributed"]] == ["para…"]


def test_groups_sharing_a_trigger_become_one_row():
    index = _index(speech(1, "what is going on", 1_000),
                   *[chat(i, t, 2_000 + i) for i, t in
                     enumerate(["violet", "Violet", "VIOLET", "violet.",
                                "is that violet", "violet myers", "VIOLET MY GOAT"])],
                   *[chat(20 + i, t, 3_000 + i) for i, t in
                     enumerate(["wtf", "WTF", "wtf..."])])

    rows = board(index, 0, 60_000)["rows"]

    assert len(rows) == 1
    assert sorted(g["label"] for g in rows[0]["groups"]) == ["violet", "wtf"]
    assert rows[0]["count"] == 10


def test_the_footer_says_how_much_was_left_out():
    """Six rows out of 237 messages read as the whole window unless the board says otherwise."""
    index, start, end = _window("marlon_2026-08-30T0715", 6)

    footer = board(index, start, end)["footer"]

    assert footer == {"messages": 237, "rows": 4, "singletons": 123, "rows_hidden": 0}


def test_the_flagship_row_reproduces_on_the_recorded_fixture():
    """marlon w6: the streamer is mid-sentence asking what is going on and 27 people have
    already typed the name of who walked on screen."""
    index, start, end = _window("marlon_2026-08-30T0715", 6)

    row = board(index, start, end)["rows"][0]
    violet = next(g for g in row["groups"] if g["label"] == "violet")

    assert row["trigger"]["kind"] == "speech"
    assert violet["count"] == 27
    assert violet["samples"] == ["violet murders?", "VIOLET MYERS", "VIOLET."]


def test_the_word_game_window_matches_its_caption():
    """stableronaldo w0: the caption names the guessed word and chat is brute-forcing it. The
    only `matched` row on that fixture's first window, and the thesis in one line."""
    index, start, end = _window("stableronaldo_2026-08-30T0723", 0)

    matched = [r for r in board(index, start, end)["rows"]
               if r["trigger"]["link"] == "matched"]

    assert len(matched) == 1
    assert "ranger" in matched[0]["trigger"]["text"]
    assert matched[0]["groups"][0]["label"] == "rang…"


def test_the_board_is_deterministic():
    index, start, end = _window("marlon_2026-08-30T0715", 6)

    assert board(index, start, end) == board(index, start, end)


# ----------------------------------------------------------------------------------- questions

def test_a_question_needs_a_content_word():
    """The bare `ends with ?` rule returns 54 hits on one marlon window and they are almost all
    literally `???`. Punctuation is volume, not a question."""
    assert is_question("what game is this")
    assert is_question("has he played yet?")
    assert not is_question("???")
    assert not is_question("?")
    assert not is_question("is it?")            # 'is' and 'it' are both stopwords


def test_questions_are_grouped_so_twenty_phrasings_count_once():
    asked = [chat(i, t, 1_000 + i) for i, t in
             enumerate(["what game is this", "whats the game", "what game are we playing",
                        "yo what game", "when is the stream ending"])]

    ranked = questions(asked)

    assert ranked[0]["count"] == 4
    assert ranked[0]["variants"][0] == "what game is this"
    assert ranked[-1]["count"] == 1


def test_a_window_with_no_questions_returns_nothing():
    assert questions([chat(1, "LOL", 1_000), chat(2, "parade", 1_100)]) == []


# --------------------------------------------------------------------------------------- rail

def test_the_rail_counts_what_the_raw_message_count_hides():
    """Whether 500 messages is five people or five hundred is a completely different fact."""
    index = _index(*[chat(i, f"msg {i}", 1_000 + i, author="loud") for i in range(9)],
                   chat(99, "hello there", 2_000, author="quiet"))

    stats = rail(index, 0, 60_000)

    assert stats["messages"] == 10
    assert stats["unique_chatters"] == 2
    assert stats["messages_per_chatter"] == 5.0
    assert stats["concentration"] == 0.9


def test_new_chatters_are_new_relative_to_what_came_before():
    index = _index(chat(1, "hi there", 1_000, author="old"),
                   chat(2, "hello all", 1_100, author="new"))

    assert rail(index, 0, 60_000, seen_authors={"old"})["new_chatters"] == 1


def test_the_rate_sparkline_buckets_by_ten_seconds():
    index = _index(chat(1, "a", 0), chat(2, "b", 5_000), chat(3, "c", 25_000))

    stats = rail(index, 0, 30_000)

    assert stats["rate"] == [2, 0, 1]
    assert stats["peak_burst"] == 2 and stats["peak_per_second"] == 0.2


def test_a_silent_window_is_stated_not_left_blank():
    """Zero speech segments is the truth on stableronaldo, and it is a finding about the stream
    rather than a hole in the data."""
    index, start, end = _window("stableronaldo_2026-08-30T0723", 9)

    stats = rail(index, start, end)

    assert stats["speech_segments"] == 0 and stats["silent"] is True
    assert len(stats["frame_captions"]) == 2


def test_the_gate_ledger_counts_the_agents_cards_by_code():
    cards = [{"gate": {"ok": True}, "type": "reaction"},
             {"gate": {"ok": True}, "type": "none"},
             {"gate": {"ok": False, "violations": [{"code": "E_CIRCULAR_EVIDENCE"}]}},
             {"gate": {"ok": False, "violations": [{"code": "E_CIRCULAR_EVIDENCE"}]}}]

    ledger = rail(_index(chat(1, "hi there", 0)), 0, 60_000, cards=cards)["gate"]

    assert ledger == {"verified": 1, "abstained": 1, "rejected": 2,
                      "codes": {"E_CIRCULAR_EVIDENCE": 2}}


def test_the_rail_holds_up_with_an_empty_window():
    stats = rail(_index(), 0, 60_000)

    assert stats["messages"] == 0 and stats["unique_chatters"] == 0
    assert stats["concentration"] == 0.0 and stats["questions"] == []
