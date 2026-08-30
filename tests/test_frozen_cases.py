"""The frozen evaluation set.

Gold labels are the measuring instrument. A gold file pointing at an id that does not exist
scores every card as a miss and the failure is silent — the run completes, the table fills, and
the numbers are meaningless. These tests make that failure loud.

The strongest check here is not "the ids exist" but "a card built from this gold survives the
provenance gate". If the gold itself cannot pass the gate, no correct system can match it.
"""
import json
from pathlib import Path

import pytest

from ts.ingest.replay import load_fixture
from ts.provenance import check_card

REPO = Path(__file__).resolve().parents[1]
CASES, GOLD, FIXTURES = REPO / "evals" / "cases", REPO / "evals" / "gold", REPO / "evals" / "fixtures"

CARD_TYPES = {"audience_answer", "reaction", "unanswered_question", "warning", "none"}
CASE_FILES = sorted(CASES.glob("*.json"))
_INDEX: dict = {}


def index(name):
    if name not in _INDEX:
        _INDEX[name] = load_fixture(FIXTURES / name)
    return _INDEX[name]


def gold_of(case_id):
    return json.loads((GOLD / f"{case_id}.json").read_text(encoding="utf-8"))


def ids():
    return [p.stem for p in CASE_FILES]


def test_the_frozen_set_is_big_enough_to_measure():
    assert len(CASE_FILES) >= 10, "the protocol calls for 10-12 cases"


def test_every_case_has_exactly_one_gold_file():
    assert ids() == sorted(p.stem for p in GOLD.glob("*.json"))


@pytest.mark.parametrize("case_id", ids())
def test_no_reported_case_rests_on_a_synthetic_fixture(case_id):
    """The synthetic scaffold exists so the repo runs on first clone. It must never be the
    source of a reported number, and `make eval` banners any case that is."""
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    assert case["fixture_kind"] == "capture"
    assert (FIXTURES / case["fixture"] / "meta.json").exists()


@pytest.mark.parametrize("case_id", ids())
def test_case_and_gold_agree_on_fixture_and_window(case_id):
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    g = gold_of(case_id)
    assert (g["fixture"], g["window_ms"]) == (case["fixture"], case["window_ms"])


@pytest.mark.parametrize("case_id", ids())
def test_every_gold_signal_would_survive_the_provenance_gate(case_id):
    """The load-bearing one. Trigger real and not itself a chat message, evidence real, all of
    it inside the half-open window, trigger not after the messages it supposedly caused."""
    g = gold_of(case_id)
    ix = index(g["fixture"])
    start, end = g["window_ms"]

    for i, sig in enumerate(g["gold_signals"]):
        assert sig["type"] in CARD_TYPES
        trigger = sig["trigger_event_id"]
        if trigger != "unknown":
            ev = ix.get(trigger)
            assert ev is not None, f"{case_id} sig{i}: trigger {trigger} not in fixture"
            assert ev.type != "chat_message", "a chat message cannot be its own cause"
        for mid in sig["relevant_message_ids"]:
            msg = ix.get(mid)
            assert msg is not None, f"{case_id} sig{i}: {mid} not in fixture"
            assert msg.type == "chat_message", f"{case_id}: {mid} is {msg.type}"
            assert start <= msg.ts_ms < end, f"{case_id}: {mid} outside the half-open window"

        card = {"signal_id": f"g{i}", "type": sig["type"], "window_ms": [start, end],
                "evidence": sig["relevant_message_ids"],
                "trigger": {"kind": "speech", "event_id": trigger}}
        result = check_card(card, ix)
        assert result.ok, f"{case_id} sig{i}: the gate rejects its own gold -> {result.codes}"


@pytest.mark.parametrize("case_id", ids())
def test_abstention_cases_carry_no_signals_and_vice_versa(case_id):
    g = gold_of(case_id)
    assert bool(g["must_abstain"]) == (len(g["gold_signals"]) == 0)


@pytest.mark.parametrize("case_id", ids())
def test_label_provenance_is_declared_rather_than_implied(case_id):
    """These labels were drafted with model assistance and no human has confirmed them yet.
    Claiming human ground truth we do not have would be the one unrecoverable mistake here."""
    g = gold_of(case_id)
    assert "reviewed" in g, "every gold file states its review status"
    assert isinstance(g["reviewed"], bool)


def test_the_three_cases_the_product_wins_on_are_present():
    """Warning with no provable cause, sarcasm, and abstention. Everything else is table stakes;
    these three are where a grounded system beats a fluent one."""
    have = " ".join(ids())
    assert "warning_no_cause" in have
    assert "sarcasm" in have
    assert "abstain" in have


def test_at_least_one_case_has_no_speech_at_all():
    """The thesis is that chat is uninterpretable without the screen. A case with zero
    transcript segments is the only way to prove a speech-only system could not have solved it."""
    silent = []
    for case_id in ids():
        g = gold_of(case_id)
        start, end = g["window_ms"]
        speech = index(g["fixture"]).window(start, end, types=["transcript_segment"])
        if not speech and g["gold_signals"]:
            silent.append(case_id)
    assert silent, "no case proves the frame-only path"


def test_more_than_one_fixture_is_represented():
    """Twelve cases off one broadcast would measure one streamer, not the product."""
    fixtures = {gold_of(c)["fixture"] for c in ids()}
    assert len(fixtures) >= 3, f"only {len(fixtures)} fixture(s) behind the whole eval"
