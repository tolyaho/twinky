from evals.scorer import aggregate, score_case
from ts.events import Event, EventIndex


def idx():
    return EventIndex([
        Event("tr_1", "transcript_segment", 1000, {"text": "в лес или на базу?"}),
        Event("msg_1", "chat_message", 2000, {"text": "лес"}),
        Event("msg_2", "chat_message", 2100, {"text": "база"}),
    ])


GOLD = {"gold_signals": [{"type": "audience_answer", "trigger_event_id": "tr_1",
                          "relevant_message_ids": ["msg_1", "msg_2"]}],
        "must_abstain": False}


def card(**kw):
    base = {"signal_id": "s", "type": "audience_answer", "window_ms": [0, 5000],
            "trigger": {"kind": "speech", "event_id": "tr_1", "quote": "в лес или на базу"},
            "evidence": ["msg_1", "msg_2"]}
    base.update(kw)
    return base


def test_perfect_card_scores_clean():
    s = score_case(case_id="c1", system="agent", cards=[card()], gold=GOLD, index=idx())
    assert s.trigger_accuracy == 1.0
    assert s.unsupported_rate == 0.0
    assert s.signal_recall == 1.0


def test_wrong_trigger_costs_accuracy_but_may_still_be_supported():
    c = card(trigger={"kind": "unknown", "event_id": "unknown", "quote": None})
    s = score_case(case_id="c1", system="baseline", cards=[c], gold=GOLD, index=idx())
    assert s.trigger_accuracy == 0.0
    assert s.unsupported_rate == 0.0


def test_hallucinated_evidence_counts_as_unsupported():
    s = score_case(case_id="c1", system="baseline",
                   cards=[card(evidence=["msg_1", "ghost"])], gold=GOLD, index=idx())
    assert s.unsupported_rate == 1.0


def test_abstention_case():
    gold = {"gold_signals": [], "must_abstain": True}
    ok = score_case(case_id="c9", system="agent",
                    cards=[{"type": "none", "evidence": ["msg_1"], "window_ms": [0, 5000]}],
                    gold=gold, index=idx())
    bad = score_case(case_id="c9", system="baseline", cards=[card()], gold=gold, index=idx())
    assert ok.abstain_correct is True
    assert bad.abstain_correct is False


def test_aggregate_across_cases():
    a = score_case(case_id="c1", system="agent", cards=[card()], gold=GOLD, index=idx())
    b = score_case(case_id="c2", system="agent",
                   cards=[card(evidence=["ghost"])], gold=GOLD, index=idx())
    agg = aggregate([a, b])
    assert agg["cases"] == 2 and agg["cards"] == 2
    assert agg["unsupported_rate"] == 0.5


# --------------------------------------------------------------------------- matching is 1:1
def _gold(**overrides):
    g = {"gold_signals": [{"type": "audience_answer", "trigger_event_id": "tr_1",
                           "relevant_message_ids": ["msg_1", "msg_2"]}],
         "must_abstain": False}
    g.update(overrides)
    return g


def _card(sid, *, typ="audience_answer", trigger="tr_1", evidence=("msg_1",)):
    return {"signal_id": sid, "type": typ, "window_ms": [0, 10_000],
            "evidence": list(evidence), "trigger": {"kind": "speech", "event_id": trigger}}


def test_a_gold_signal_can_only_be_found_once():
    """Emitting the same card twice used to weight that one gold signal twice in trigger
    accuracy. A signal can be found once; the duplicate is a card that matched nothing."""
    index = idx()

    score = score_case(case_id="c", system="a", cards=[_card("s0"), _card("s1")],
                       gold=_gold(), index=index)

    assert score.trigger_scored == 1
    assert score.unmatched == 1
    assert score.signal_recall_hits == 1


def test_noise_cannot_lower_trigger_accuracy_but_is_reported_beside_it():
    """The denominator is matched cards, so hallucinations do not touch metric A. That is a real
    hole in the metric taken alone, which is why `unmatched_rate` sits next to it."""
    index = idx()
    noise = [_card(f"n{i}", typ="reaction", trigger="tr_1", evidence=["msg_2"]) for i in range(9)]

    score = score_case(case_id="c", system="a", cards=[_card("s0")] + noise,
                       gold=_gold(), index=index)
    agg = aggregate([score])

    assert agg["trigger_accuracy"] == 1.0
    assert agg["unmatched_rate"] == 0.9


def test_unmatched_rate_is_zero_when_every_card_lands():
    score = score_case(case_id="c", system="a", cards=[_card("s0")], gold=_gold(), index=idx())

    assert score.unmatched == 0
    assert aggregate([score])["unmatched_rate"] == 0.0


def test_the_row_carries_the_new_column():
    row = score_case(case_id="c", system="a", cards=[_card("s0")],
                     gold=_gold(), index=idx()).to_row()

    assert "unmatched_rate" in row and "unmatched" in row
