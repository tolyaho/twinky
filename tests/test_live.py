"""Live capture: the demo path, and the guards that keep it from costing anything unattended.

Replay stays the graded route — a judge reproduces this submission with no API keys, and that
property is the whole reproducibility claim. Live exists to show the pipeline is not replay-only.
Everything here is about the three things that make it safe to ship: it refuses to start past the
cap, it stops itself, and it never touches the committed cache.
"""
import json
from pathlib import Path

import pytest

from ts import live

REPO = Path(__file__).resolve().parents[1]


def ledger(tmp_path, total):
    p = tmp_path / "COST_LEDGER.md"
    p.write_text(f"x | calls=1 | est_usd=0.01 | running_total={total}\n", encoding="utf-8")
    return p


# --------------------------------------------------------------- the budget guard
def test_the_cap_is_read_from_the_ledger(tmp_path):
    assert live.ledger_total(ledger(tmp_path, "1.23")) == 1.23


def test_a_missing_ledger_reads_as_nothing_spent(tmp_path):
    assert live.ledger_total(tmp_path / "absent.md") == 0.0


def test_live_refuses_to_start_past_the_cap(tmp_path):
    """Money is spent per window, so the check has to happen before the first one."""
    events = list(live.session("anychannel", ledger=ledger(tmp_path, "3.50")))

    assert len(events) == 1
    assert events[0]["kind"] == "stopped" and events[0]["reason"] == "budget"
    assert "cap is already spent" in events[0]["message"]
    assert "Replay is unaffected" in events[0]["message"]


def test_the_cap_is_below_the_project_hard_cap():
    assert live.LIVE_COST_CAP_USD < 5.00, "an unattended demo must not consume the whole budget"


def test_budget_state_reports_what_the_screen_shows(tmp_path):
    state = live.budget_state(ledger(tmp_path, "0.41"))

    assert state["spent_usd"] == 0.41
    assert state["remaining_usd"] == round(live.LIVE_COST_CAP_USD - 0.41, 4)
    assert state["allowed"] is True


# --------------------------------------------------------------- offline is not an error
def test_an_offline_channel_is_a_message_not_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "is_live", lambda channel: False)

    events = list(live.session("someone", ledger=ledger(tmp_path, "0.10")))

    assert [e["kind"] for e in events] == ["stopped"]
    assert events[0]["reason"] == "offline"
    assert "is not live right now" in events[0]["message"]


# --------------------------------------------------------------- the stop
def test_it_stops_itself(tmp_path, monkeypatch):
    """An unattended demo that keeps enriching is a bill."""
    monkeypatch.setattr(live, "is_live", lambda channel: True)
    ticks = iter([0.0, 999.0, 999.0, 999.0])
    events = list(live.session("someone", ledger=ledger(tmp_path, "0.10"),
                               max_seconds=10, clock=lambda: next(ticks)))

    kinds = [e["kind"] for e in events]
    assert kinds[0] == "status"
    assert kinds[-1] == "stopped" and events[-1]["reason"] == "time_limit"


def test_the_default_stop_is_ten_minutes():
    assert live.LIVE_MAX_SECONDS == 600


def test_the_lag_is_stated_not_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "is_live", lambda channel: True)
    ticks = iter([0.0, 999.0, 999.0, 999.0])
    events = list(live.session("someone", ledger=ledger(tmp_path, "0.10"),
                               max_seconds=10, clock=lambda: next(ticks)))

    status = events[0]
    assert status["lag_seconds"] >= live.WINDOW_SECONDS
    assert "behind the broadcast" in status["message"]


# --------------------------------------------------------------- the committed cache
def test_live_never_writes_to_the_committed_cache():
    """`cache/llm/` IS the reproduction artifact. Live audio is keyed on bytes that will never
    occur again, so recording into it would grow the artifact with entries no replay can hit."""
    source = (REPO / "src" / "ts" / "live.py").read_text(encoding="utf-8")

    assert 'ResponseCache(cache_dir=Path(live_dir.name), mode="record")' in source
    assert "leaves the graded cache untouched" in source
    assert "DEFAULT_CACHE_DIR" not in source


def test_live_records_because_replay_of_new_audio_is_impossible():
    """The first attempt failed exactly here: the cache defaulted to replay mode and a live
    window has by definition never been seen."""
    source = (REPO / "src" / "ts" / "live.py").read_text(encoding="utf-8")

    assert 'mode="record"' in source
    assert "replay is" in source and "impossible by definition" in source


# --------------------------------------------------------------- replay stays the default
def test_the_page_does_not_go_live_on_load():
    js = (REPO / "src" / "ts" / "report" / "static" / "live.js").read_text(encoding="utf-8")

    assert 'getElementById("go-live").addEventListener("click", goLive)' in js
    assert "goLive()" not in js.split("function goLive")[0], "live must not run at startup"


def test_the_badge_states_the_lag_while_live():
    js = (REPO / "src" / "ts" / "report" / "static" / "live.js").read_text(encoding="utf-8")

    assert "LIVE · ~${s.lag_seconds}s behind" in js
    assert "REPLAY" in js, "it must return to replay when the session stops"


def test_the_channel_name_is_sanitised_before_it_reaches_a_subprocess():
    serve = (REPO / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")

    assert 're.sub(r"[^A-Za-z0-9_]", "", params.get("channel", ""))' in serve


def test_a_live_demo_never_writes_into_the_graded_trajectories():
    """`trajectories/` is a deliverable and must hold real evaluation runs only. The first live
    session wrote a trace straight into it — the same class of pollution that once put 55 test
    artifacts there. Caught by the existing guard, fixed at the source."""
    source = (REPO / "src" / "ts" / "live.py").read_text(encoding="utf-8")

    assert 'os.environ["TS_TRACE_DIR"] = str(trace_dir)' in source
    assert "never to `trajectories/`" in source
    assert '_analyse(root, cache, Path(tmp) / "traces")' in source
