"""Regressions found in the independent review, using actual frozen results/cache."""
import asyncio
import hashlib
import json
from pathlib import Path
import pytest
from ts.cache import ResponseCache
from ts.events import Event, EventIndex
from ts.ingest.replay import load_fixture
from ts.provenance import GATE_V1, GATE_V2, check_card
from ts.report.board import answered_by
from ts.report.results import load_result
from ts.workflow.trace import Trace

ROOT = Path(__file__).resolve().parents[1]


def test_replay_cannot_see_a_future_answer_or_unfinished_segment():
    index = EventIndex([Event("s", "transcript_segment", 90_000,
                              {"text": "the blue controller is here", "end_ms": 95_000})])
    q = {"ts_ms": 0, "text": "where is the blue controller?"}
    assert answered_by(index, q, as_of_ms=60_000) is None
    assert answered_by(index, q, as_of_ms=91_000) is None
    assert answered_by(index, q, as_of_ms=95_000)["event_id"] == "s"


def test_entire_replay_never_emits_a_question_answer_from_the_future():
    from ts.report.serve import stream_events
    fixture = ROOT / "evals/fixtures/yugi_2026-08-30T0723"
    index = load_fixture(fixture)
    origin = next(e.ts_ms for e in index if e.type == "chat_message")
    checked = 0
    for offset, event in stream_events(fixture, ROOT / "evidence/raw-results"):
        if event["kind"] != "board":
            continue
        for q in event["questions"]["questions"]:
            if q["answered"]:
                checked += 1
                assert index.get(q["answered"]["event_id"]).end_ms <= origin + offset
    assert checked > 0


def test_replay_preserves_recorded_latencies_and_writes_a_separate_trace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TS_LLM_MODE", "record")
    recorded = Trace("agent", "case", out_dir=tmp_path / "recorded")
    recorded._t0 -= .1
    recorded.instructions("instructions", "input")
    path = recorded.write()
    before = path.read_bytes()
    assert json.loads(before)["duration_ms"] >= 100
    monkeypatch.setenv("TS_LLM_MODE", "replay")
    replay = Trace("agent", "case", out_dir=tmp_path / "recorded")
    replay.instructions("instructions", "input")
    derived = replay.write()
    assert path.read_bytes() == before
    assert derived != path and json.loads(derived.read_text())["duration_ms"] is None
    assert replay.write() == derived


def test_dashboard_projects_current_gate_without_mutating_recordings():
    fixture = ROOT / "evals/fixtures/stableronaldo_2026-08-30T0723"
    path = ROOT / "evidence/raw-results" / (fixture.name + ".agent.json")
    before = path.read_bytes()
    index = load_fixture(fixture)
    result = load_result(path, index)
    assert result["projection"]["gate_version"] == GATE_V2
    assert result["projection"]["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["counts"]["verified"] == 10
    for w in result["windows"]:
        for c in w["verified"] + w["rejected"]:
            assert c["gate"]["ok"] == check_card(c, index).ok
    assert path.read_bytes() == before


def test_h1_raw_cards_replay_from_cache_and_gate_versions_explain_the_difference(tmp_path):
    from evals.h1 import arm
    from evals.run_eval import emitted, load_cases
    from ts.workflow.agent import AudienceSignalAgent
    old = json.loads((ROOT / "evidence/h1/predictions.json").read_text())
    historical = {r["case_id"]: r for r in old if r["system"] == "agent"}
    cache = ResponseCache(mode="replay")
    totals = {GATE_V1: 0, GATE_V2: 0}
    changed = 0
    def raw(c):
        return {k: v for k, v in c.items() if k not in {"gate", "status", "action"}}
    with arm():
        for case in load_cases():
            index = load_fixture(ROOT / "evals/fixtures" / case["fixture"])
            result = AudienceSignalAgent(index, cache).run(case["case_id"], *case["window_ms"])
            cards = emitted(result)
            assert [raw(c) for c in cards] == [raw(c) for c in historical[case["case_id"]]["cards"]]
            for c in cards:
                checks = {v: check_card(c, index, version=v).ok for v in totals}
                for version, ok in checks.items():
                    totals[version] += not ok
                changed += checks[GATE_V1] != checks[GATE_V2]
    assert cache.misses == 0 and cache.hits > 0
    assert totals == {GATE_V1: 25, GATE_V2: 5} and changed == 20


def test_capture_failure_cancels_and_awaits_chat(tmp_path, monkeypatch):
    from ts.ingest import capture
    stopped = []
    async def chat(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)
    def media(*args, **kwargs):
        raise RuntimeError("media failed")
    monkeypatch.setattr(capture, "capture_chat", chat)
    monkeypatch.setattr(capture, "capture_media", media)
    monkeypatch.setattr(capture, "_salt", lambda: "test-only")
    with pytest.raises(RuntimeError, match="media failed"):
        asyncio.run(capture.capture("channel", 1, tmp_path))
    assert stopped == [True]


def test_replay_http_labels_cannot_inherit_paid_provider_mode(tmp_path, monkeypatch):
    from ts.cache import CacheMiss
    from ts.report import serve
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TS_LLM_MODE", "record")
    monkeypatch.setattr(serve, "_LABEL_CACHE", None)
    cache = serve._label_cache()
    def forbidden(request):
        pytest.fail("replay HTTP route reached a paid provider")
    with pytest.raises(CacheMiss):
        cache.call({"model": "missing-test-recording"}, forbidden)
    assert cache.mode == "replay"
