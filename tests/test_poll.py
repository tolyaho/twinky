"""The one outward action: approve → draft poll.

This is the last link of the product invariant, and the one place where the system produces
something aimed at the audience rather than at the streamer. So the tests are mostly about
restraint: nothing posts, nothing is silently trimmed, and a card that cannot honestly become a
poll does not become one.
"""
import json
import shutil
from pathlib import Path

import pytest

from ts.report import poll
from ts.report.serve import STATIC, payload

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"


def card(**overrides):
    base = {
        "signal_id": "sig_00", "type": "audience_answer", "title": "Chat says лес",
        "distribution": {"лес": 9, "база": 6},
        "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
        "evidence": ["msg_0001", "msg_0002"], "confidence": 0.86, "trace_id": "trc_a",
        "action": {"kind": "draft_poll", "state": "pending_approval"},
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- the draft
def test_the_question_is_what_the_streamer_actually_said():
    draft = poll.build_draft(card())

    assert draft["question"] == "в лес или на базу?"
    assert draft["state"] == "pending_approval"
    assert draft["posts_anything"] is False
    assert draft["warnings"] == []


def test_options_are_ordered_by_votes_then_label():
    draft = poll.build_draft(card(distribution={"b": 3, "a": 3, "c": 9}))

    assert [o["label"] for o in draft["options"]] == ["c", "a", "b"]
    assert draft["options"][0]["share"] == 0.6


def test_a_card_with_no_established_cause_says_so_instead_of_inventing_a_question():
    draft = poll.build_draft(card(trigger={"kind": "unknown", "event_id": "unknown"}))

    assert draft["question"] == "Chat says лес"          # the title, not a fabricated quote
    assert any("No established cause" in w for w in draft["warnings"])


def test_one_option_is_not_a_poll():
    assert poll.build_draft(card(distribution={"лес": 9})) is None


def test_zero_counts_are_not_a_poll():
    assert poll.build_draft(card(distribution={"лес": 0, "база": 0})) is None


def test_only_audience_answers_become_polls():
    assert poll.build_draft(card(type="reaction")) is None


# --------------------------------------------------------------------------- no silent caps
def test_dropped_options_are_named_not_silently_trimmed():
    draft = poll.build_draft(card(distribution={c: n for n, c in enumerate("abcdefg", start=1)}))

    assert len(draft["options"]) == poll.MAX_OPTIONS
    warning = " ".join(draft["warnings"])
    assert "7 options" in warning
    assert "a" in warning and "b" in warning     # the two dropped, named


def test_a_shortened_option_reports_what_it_was():
    long = "a" * 40
    draft = poll.build_draft(card(distribution={long: 9, "база": 6}))

    assert len(draft["options"][0]["label"]) == poll.MAX_OPTION_CHARS
    assert any("shortened" in w for w in draft["warnings"])


def test_the_draft_is_the_same_every_time():
    first, second = poll.build_draft(card()), poll.build_draft(card())

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# --------------------------------------------------------------------------- attachment
def test_a_draft_is_attached_only_where_the_agent_asked_for_an_action():
    cards = [card(), card(signal_id="sig_01", action=None), card(signal_id="sig_02", type="warning")]

    assert poll.attach_drafts(cards) == 1
    assert "poll_draft" in cards[0]
    assert "poll_draft" not in cards[1] and "poll_draft" not in cards[2]


def test_the_served_payload_carries_the_draft(tmp_path):
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "sample.agent.json").write_text(json.dumps({
        "windows": [{"verified": [card()], "rejected": []}]}), encoding="utf-8")

    got = payload(tmp_path / "fixture", tmp_path / "out")

    served = got["result"]["windows"][0]["verified"][0]
    assert served["poll_draft"]["question"] == "в лес или на базу?"


# --------------------------------------------------------------------------- nothing posts
def test_the_module_has_no_client_no_token_and_no_request():
    """Ground rule 06: polls, highlights and replies stay drafts. The cheapest way to keep that
    true is for the code path to contain nothing capable of sending."""
    source = Path(poll.__file__).read_text(encoding="utf-8")

    for forbidden in ("httpx", "requests", "urllib", "socket", "post(", "TOKEN", "api_key"):
        assert forbidden not in source, forbidden


def test_the_approve_button_sends_nothing():
    js = (STATIC / "method.js").read_text(encoding="utf-8")
    approval = js[js.index("function approval"):js.index("function renderCard")]

    assert "fetch(" not in approval
    assert "XMLHttpRequest" not in approval
    assert "Nothing was posted" in approval
    assert "Approve → draft poll" in approval


def test_shares_count_every_vote_even_when_options_are_dropped():
    """A share renormalised over the surviving options would print a percentage that disagrees
    with the card sitting directly above it on the page."""
    draft = poll.build_draft(card(distribution={c: n for n, c in enumerate("abcdefg", start=1)}))

    assert draft["total_votes"] == 28                      # 1+2+…+7, nothing hidden
    assert draft["options"][0] == {"label": "g", "votes": 7, "share": 0.25}
    assert sum(o["share"] for o in draft["options"]) < 1.0
    assert "do not add to 100%" in " ".join(draft["warnings"])
