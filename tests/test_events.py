import pytest
from ts.events import Event, EventIndex, make_event_id, order, window


def ev(eid, ts, typ="chat_message", text="x", final=True):
    return Event(event_id=eid, type=typ, ts_ms=ts, payload={"text": text}, final=final)


def test_total_order_is_stable_and_not_insertion_order():
    a = order([ev("z", 300), ev("a", 100), ev("m", 200)])
    b = order([ev("m", 200), ev("z", 300), ev("a", 100)])
    assert [e.event_id for e in a] == [e.event_id for e in b] == ["a", "m", "z"]


def test_order_breaks_ties_deterministically():
    # same timestamp: ordering must still be identical across runs
    a = order([ev("b", 100), ev("a", 100)])
    assert [e.event_id for e in a] == ["a", "b"]


def test_window_is_half_open():
    evs = [ev("a", 100), ev("b", 200), ev("c", 300)]
    got = [e.event_id for e in window(evs, 100, 300)]
    assert got == ["a", "b"]  # 300 excluded


def test_window_final_only_filters_interim():
    """The legacy summary builder omitted this filter, so interim and final phrases
    both entered context and duplicated content."""
    evs = [ev("i", 100, "transcript_segment", "я сегодня", final=False),
           ev("f", 110, "transcript_segment", "я сегодня поел", final=True)]
    got = [e.event_id for e in window(evs, 0, 1000, final_only=True)]
    assert got == ["f"]


def test_event_ids_derive_from_content_not_wall_clock():
    assert make_event_id("frm", 1234, "a") == make_event_id("frm", 1234, "a")
    assert make_event_id("frm", 1234, "a") != make_event_id("frm", 1235, "a")


def test_index_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        EventIndex([ev("dup", 1), ev("dup", 2)])


def test_index_lookup():
    idx = EventIndex([ev("a", 100), ev("b", 200)])
    assert len(idx) == 2
    assert idx.get("a").ts_ms == 100
    assert idx.get("nope") is None
    assert (idx.start_ms, idx.end_ms) == (100, 200)
