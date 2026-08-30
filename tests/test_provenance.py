from ts.events import Event, EventIndex
from ts.provenance import apply_gate, check_card, normalize


def _index():
    return EventIndex([
        Event("tr_1", "transcript_segment", 1000, {"text": "куда идти - в лес или на базу?"}),
        Event("msg_1", "chat_message", 2000, {"text": "лес", "author": "u1"}),
        Event("msg_2", "chat_message", 2100, {"text": "база", "author": "u2"}),
        Event("msg_3", "chat_message", 9000, {"text": "оверлей закрывает миникарту", "author": "u3"}),
    ])


def _card(**kw):
    base = {
        "signal_id": "s1", "type": "audience_answer", "title": "t",
        "window_ms": [0, 5000],
        "trigger": {"kind": "speech", "event_id": "tr_1", "quote": "в лес или на базу"},
        "evidence": ["msg_1", "msg_2"],
    }
    base.update(kw)
    return base


def test_good_card_passes():
    assert check_card(_card(), _index()).ok


def test_missing_evidence_rejected():
    r = check_card(_card(evidence=[]), _index())
    assert not r.ok and "E_NO_EVIDENCE" in r.codes


def test_hallucinated_message_id_rejected():
    r = check_card(_card(evidence=["msg_1", "msg_999"]), _index())
    assert not r.ok and "E_UNKNOWN_MSG" in r.codes


def test_evidence_outside_claimed_window_rejected():
    r = check_card(_card(evidence=["msg_1", "msg_3"]), _index())
    assert not r.ok and "E_MSG_OUT_WINDOW" in r.codes


def test_hallucinated_trigger_rejected():
    r = check_card(_card(trigger={"kind": "speech", "event_id": "tr_999", "quote": "x"}), _index())
    assert not r.ok and "E_UNKNOWN_TRIGGER" in r.codes


def test_invented_quote_rejected():
    """The exact January 2026 failure mode: a confident cause that is not in the transcript."""
    r = check_card(_card(trigger={"kind": "speech", "event_id": "tr_1",
                                  "quote": "какое оружие мне взять"}), _index())
    assert not r.ok and "E_QUOTE_MISMATCH" in r.codes


def test_trigger_after_its_effect_rejected():
    idx = EventIndex([
        Event("tr_late", "transcript_segment", 5000, {"text": "ну и как вам"}),
        Event("msg_1", "chat_message", 2000, {"text": "лес"}),
    ])
    r = check_card(_card(evidence=["msg_1"],
                         trigger={"kind": "speech", "event_id": "tr_late", "quote": "ну и как вам"}),
                   idx)
    assert not r.ok and "E_TRIGGER_LATE" in r.codes


def test_unknown_trigger_is_legitimate():
    """Abstention is correct behaviour, not a failure."""
    card = _card(type="warning", trigger={"kind": "unknown", "event_id": "unknown", "quote": None},
                 evidence=["msg_1"])
    assert check_card(card, _index()).ok


def test_quote_tolerates_punctuation_drift():
    card = _card(trigger={"kind": "speech", "event_id": "tr_1", "quote": "В ЛЕС, ИЛИ НА БАЗУ!"})
    assert check_card(card, _index()).ok


def test_apply_gate_partitions_and_measures():
    good, bad = _card(), _card(signal_id="s2", evidence=["nope"])
    out = apply_gate([good, bad], _index())
    assert len(out["verified"]) == 1 and len(out["rejected"]) == 1
    assert out["unsupported_rate"] == 0.5
    assert out["rejected"][0]["status"] == "rejected"


def test_normalize():
    assert normalize("  ПРИВЕТ,  Мир!! ") == "привет мир"


# --------------------------------------------------------------------------- window boundary
def test_the_gate_and_the_tools_agree_on_the_window_boundary():
    """The gate used an inclusive end while `events.window` is half-open, so a card could cite
    a message at the boundary that the agent's own tools never returned for that window — and
    tiles are adjacent, so that message belonged to the next one."""
    from ts.events import Event, EventIndex
    from ts.workflow.tools import Tools

    boundary = 5000
    index = EventIndex([
        Event(event_id="msg_in", type="chat_message", ts_ms=boundary - 1, payload={"text": "a"}),
        Event(event_id="msg_edge", type="chat_message", ts_ms=boundary, payload={"text": "b"}),
    ])
    window = [0, boundary]

    visible = {m["id"] for m in Tools(index).get_chat_window(*window)}
    assert visible == {"msg_in"}

    card = {"type": "reaction", "window_ms": window, "evidence": ["msg_edge"],
            "trigger": {"event_id": "unknown"}}
    result = check_card(card, index)

    assert "E_MSG_OUT_WINDOW" in result.codes
    assert check_card({**card, "evidence": ["msg_in"]}, index).ok


def test_the_window_start_is_still_inclusive():
    from ts.events import Event, EventIndex

    index = EventIndex([Event(event_id="msg_start", type="chat_message", ts_ms=1000,
                              payload={"text": "a"})])

    assert check_card({"type": "reaction", "window_ms": [1000, 2000],
                       "evidence": ["msg_start"], "trigger": {"event_id": "unknown"}},
                      index).ok


# --------------------------------------------------------------------------- what counts as evidence
def _index_with_frame():
    return EventIndex([
        Event("tr_1", "transcript_segment", 1000, {"text": "куда идти - в лес или на базу?"}),
        Event("frm_1", "frame_caption", 1100, {"text": "a fork in the path"}),
        Event("msg_1", "chat_message", 2000, {"text": "лес", "author": "u1"}),
    ])


def test_a_transcript_segment_is_not_a_representative_message():
    """The gate accepted any event id, so a card could offer the streamer's own speech as the
    audience's response to it."""
    card = {"type": "reaction", "window_ms": [0, 5000], "evidence": ["tr_1"],
            "trigger": {"event_id": "unknown"}}

    assert check_card(card, _index_with_frame()).codes == ["E_EVIDENCE_NOT_A_MESSAGE"]


def test_a_frame_caption_is_not_a_representative_message():
    card = {"type": "reaction", "window_ms": [0, 5000], "evidence": ["frm_1"],
            "trigger": {"event_id": "unknown"}}

    assert check_card(card, _index_with_frame()).codes == ["E_EVIDENCE_NOT_A_MESSAGE"]


def test_a_card_cannot_cite_its_own_trigger_as_support():
    """Circular: the event that caused the signal, offered as proof of the signal."""
    card = {"type": "audience_answer", "window_ms": [0, 5000], "evidence": ["tr_1"],
            "trigger": {"kind": "speech", "event_id": "tr_1", "quote": "в лес"}}

    assert "E_CIRCULAR_EVIDENCE" in check_card(card, _index_with_frame()).codes


def test_an_honest_card_is_unaffected():
    card = {"type": "audience_answer", "window_ms": [0, 5000], "evidence": ["msg_1"],
            "trigger": {"kind": "speech", "event_id": "tr_1",
                        "quote": "в лес или на базу?"}}

    assert check_card(card, _index_with_frame()).ok
