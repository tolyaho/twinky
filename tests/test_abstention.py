"""Abstention: the behaviour the product is designed to win on.

A `none` card used to fail the gate on E_NO_EVIDENCE, because a card that claims nothing has
nothing to cite. So a correct abstention scored 1.0 on the unsupported-card rate — the headline
metric — and landed in the dashboard's rejected bin, where the demo would have shown the
product's best moment as a failure. These tests exist to keep that from coming back.
"""
import json
import shutil
from pathlib import Path

import pytest

from evals.scorer import aggregate, score_case
from ts.ingest.replay import load_fixture
from ts.provenance import apply_gate, check_card
from ts.report.serve import STATIC

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"
QUIET_WINDOW = [1756400013500, 1756400019500]      # the window case c12 abstains on


@pytest.fixture
def index():
    return load_fixture(SAMPLE)


def abstention(**overrides):
    card = {"signal_id": "sig_00", "type": "none", "title": "No signal in this window",
            "window_ms": QUIET_WINDOW}
    card.update(overrides)
    return card


# --------------------------------------------------------------------------- the gate
def test_a_correct_abstention_passes_the_gate(index):
    result = check_card(abstention(), index)

    assert result.ok and result.codes == []


def test_an_abstention_that_cites_messages_contradicts_itself(index):
    result = check_card(abstention(evidence=["msg_0001"]), index)

    assert not result.ok
    assert result.codes == ["E_NONE_WITH_EVIDENCE"]


def test_an_abstention_that_names_a_cause_contradicts_itself(index):
    result = check_card(abstention(trigger={"kind": "speech", "event_id": "tr_0001"}), index)

    assert result.codes == ["E_NONE_WITH_TRIGGER"]


def test_an_abstention_may_carry_an_explicit_unknown_trigger(index):
    """`unknown` is the system saying it found no cause, which is the same statement the card
    itself is making. That is consistent, not contradictory."""
    assert check_card(abstention(trigger={"kind": "unknown", "event_id": "unknown"}), index).ok


def test_a_passing_abstention_is_labelled_abstained_not_verified(index):
    out = apply_gate([abstention()], index)

    assert len(out["verified"]) == 1 and not out["rejected"]
    assert out["verified"][0]["status"] == "abstained"


def test_a_real_card_still_needs_evidence(index):
    """The abstention path must not become a hole in the gate."""
    result = check_card({"signal_id": "s", "type": "reaction", "window_ms": QUIET_WINDOW}, index)

    assert result.codes == ["E_NO_EVIDENCE"]


# --------------------------------------------------------------------------- the metric
def test_a_correct_abstention_no_longer_scores_as_an_unsupported_card(index):
    score = score_case(case_id="c12_no_signal_abstain", system="agent", cards=[abstention()],
                       gold={"gold_signals": [], "must_abstain": True}, index=index)

    assert score.unsupported == 0
    assert aggregate([score])["unsupported_rate"] == 0.0
    assert score.abstain_correct is True


def test_abstaining_wrongly_is_still_caught_by_the_other_metrics(index):
    """Passing abstentions through the gate must not make over-abstention free. A system that
    abstains where a signal existed keeps a clean unsupported rate and loses signal recall."""
    gold = {"gold_signals": [{"type": "audience_answer", "trigger_event_id": "tr_0001",
                              "relevant_message_ids": ["msg_0001"]}],
            "must_abstain": False}

    score = score_case(case_id="c01", system="agent", cards=[abstention()], gold=gold, index=index)

    assert score.unsupported == 0
    assert aggregate([score])["signal_recall"] == 0.0


# --------------------------------------------------------------------------- the demo
def test_the_dashboard_does_not_show_an_abstention_as_a_missing_evidence_defect():
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "Nothing to verify" in js
    assert "it is supposed to do when it cannot prove anything" in js
    assert "There is no claim here to check." in js


def test_an_abstention_renders_outside_the_rejected_block(tmp_path, index):
    """It must appear in the rail, not under 'Rejected by the provenance gate'."""
    out = apply_gate([abstention()], index)

    assert [c["signal_id"] for c in out["verified"]] == ["sig_00"]
    assert out["rejected"] == []
    assert out["unsupported_rate"] == 0.0
