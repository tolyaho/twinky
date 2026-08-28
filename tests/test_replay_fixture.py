"""The sample fixture must load and behave identically on every machine."""
from pathlib import Path

from ts.ingest.replay import load_fixture, load_meta
from ts.workflow.reduce import reduce_chat
from ts.workflow.tools import Tools

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "sample"


def test_fixture_loads():
    idx = load_fixture(FIXTURE)
    assert len(idx) == 36
    assert load_meta(FIXTURE)["fixture_id"] == "sample"


def test_load_is_deterministic():
    a = [e.event_id for e in load_fixture(FIXTURE)]
    b = [e.event_id for e in load_fixture(FIXTURE)]
    assert a == b


def test_tools_enforce_window_cap():
    idx = load_fixture(FIXTURE)
    t = Tools(idx, max_window_ms=60_000)
    ok = t.get_chat_window(idx.start_ms, idx.start_ms + 10_000)
    assert isinstance(ok, list)
    try:
        t.get_chat_window(idx.start_ms, idx.start_ms + 10_000_000)
        assert False, "window cap not enforced"
    except ValueError:
        pass


def test_reduction_actually_compresses_the_laughter_burst():
    idx = load_fixture(FIXTURE)
    laughter = idx.window(idx.start_ms + 13_000, idx.start_ms + 16_000, types=["chat_message"])
    assert len(reduce_chat(laughter)) < len(laughter)
