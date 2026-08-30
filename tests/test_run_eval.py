"""The eval runner on the frozen cases, with the provider faked.

The load-bearing assertion here is that a card the provenance gate REJECTED still reaches the
scorer. Score only the survivors and the unsupported-card rate is zero for every system by
construction, and the headline metric stops measuring anything.
"""
import csv
import json

import pytest

from evals import run_eval

# One card that clears the gate, one that cites a message that does not exist. Both are emitted;
# the gate splits them; the scorer must see both.
ANSWER = {
    "action": "answer",
    "cards": [
        {"type": "audience_answer", "title": "Chat says лес",
         "distribution": {"лес": 2, "база": 1},
         "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
         "evidence": ["msg_0001"], "confidence": 0.86},
        {"type": "warning", "title": "Invented",
         "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
         "evidence": ["msg_does_not_exist"], "confidence": 0.5},
    ],
}


class FakeDeepSeek:
    calls = 0

    def __init__(self, *a, **kw):
        pass

    def complete(self, request):
        type(self).calls += 1
        return {"choices": [{"message": {"content": json.dumps(ANSWER, ensure_ascii=False)}}]}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Cache, trajectories and evidence all land in tmp. The frozen cases and the sample fixture
    are read from the repo and never written to."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ts.providers.base.DeepSeekProvider", FakeDeepSeek)
    FakeDeepSeek.calls = 0
    return tmp_path


def _run(workspace, *extra, mode="record", monkeypatch=None):
    monkeypatch.setenv("TS_LLM_MODE", mode)
    return run_eval.main(["--cases", "c01_binary_choice", "--out", "evidence", *extra])


def test_rejected_cards_still_reach_the_scorer(workspace, monkeypatch, capsys):
    assert _run(workspace, monkeypatch=monkeypatch) == 0

    agg = json.loads(capsys.readouterr().out.split("cache:")[0])
    for system in ("baseline", "agent"):
        assert agg[system]["cards"] == 2, "the gate must not hide a card from the scorer"
        assert agg[system]["unsupported_rate"] == 0.5


def test_comparison_csv_has_one_row_per_case_and_system(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)

    rows = list(csv.DictReader((workspace / "evidence" / "comparison.csv").open(encoding="utf-8")))
    assert sorted(r["system"] for r in rows) == ["agent", "baseline"]
    assert {r["case_id"] for r in rows} == {"c01_binary_choice"}


def test_report_states_what_is_not_measured(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)

    report = (workspace / "evidence" / "report.md").read_text(encoding="utf-8")
    assert "every card they emit" in report
    assert "Latency and cost are deliberately absent" in report


def test_predictions_persist_every_card_and_its_trace(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)

    preds = json.loads((workspace / "evidence" / "predictions.json").read_text(encoding="utf-8"))
    assert len(preds) == 2
    for p in preds:
        assert p["trace_id"] and p["trace_path"]
        assert len(p["cards"]) == 2
        assert {c["gate"]["ok"] for c in p["cards"]} == {True, False}


def test_both_systems_get_the_identical_window(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)

    preds = json.loads((workspace / "evidence" / "predictions.json").read_text(encoding="utf-8"))
    assert len({tuple(p["window_ms"]) for p in preds}) == 1


def test_ablation_is_opt_in(workspace, monkeypatch):
    _run(workspace, "--ablation", monkeypatch=monkeypatch)

    preds = json.loads((workspace / "evidence" / "predictions.json").read_text(encoding="utf-8"))
    assert sorted(p["system"] for p in preds) == ["ablation_chat_only", "agent", "baseline"]


def test_eval_replays_from_cache_without_the_provider(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)
    recorded = (workspace / "evidence" / "comparison.csv").read_text(encoding="utf-8")
    calls = FakeDeepSeek.calls
    assert calls == 2  # one per system, no retries

    assert _run(workspace, mode="replay", monkeypatch=monkeypatch) == 0

    assert FakeDeepSeek.calls == calls
    assert (workspace / "evidence" / "comparison.csv").read_text(encoding="utf-8") == recorded


def test_eval_without_a_recording_exits_3_and_pays_nothing(workspace, monkeypatch, capsys):
    rc = _run(workspace, mode="replay", monkeypatch=monkeypatch)

    assert rc == 3
    assert "TS_LLM_MODE=record" in capsys.readouterr().err
    assert FakeDeepSeek.calls == 0


def test_unknown_case_selector_yields_nothing(workspace, monkeypatch):
    monkeypatch.setenv("TS_LLM_MODE", "replay")
    assert run_eval.main(["--cases", "c99_nope", "--out", "evidence"]) == 1


def test_emitted_restores_emission_order():
    result = {"verified": [{"signal_id": "sig_c_01"}], "rejected": [{"signal_id": "sig_c_00"}]}
    assert [c["signal_id"] for c in run_eval.emitted(result)] == ["sig_c_00", "sig_c_01"]


# --------------------------------------------------------------------------- case inventory
def test_every_case_has_gold_labels_and_declared_provenance():
    cases = run_eval.load_cases("all")
    assert cases, "the frozen case set must not be empty"

    for case in cases:
        gold = run_eval.load_gold(case["case_id"])
        assert gold["window_ms"] == case["window_ms"], case["case_id"]
        assert gold["fixture"] == case["fixture"], case["case_id"]
        # a case whose fixture kind is undeclared could silently become a reported number
        assert case.get("fixture_kind"), case["case_id"]


def test_gold_cites_only_events_inside_the_declared_window():
    for case in run_eval.load_cases("all"):
        index = run_eval.load_fixture(run_eval.FIXTURES_DIR / case["fixture"])
        start_ms, end_ms = case["window_ms"]
        for signal in run_eval.load_gold(case["case_id"])["gold_signals"]:
            for mid in signal["relevant_message_ids"]:
                event = index.get(mid)
                assert event is not None, f"{case['case_id']}: {mid} not in fixture"
                assert start_ms <= event.ts_ms <= end_ms, f"{case['case_id']}: {mid} out of window"
            tid = signal["trigger_event_id"]
            if tid != "unknown":
                assert index.get(tid) is not None, f"{case['case_id']}: trigger {tid} missing"


def test_abstention_case_expects_no_cards():
    gold = run_eval.load_gold("c12_no_signal_abstain")

    assert gold["must_abstain"] is True
    assert gold["gold_signals"] == []


def test_report_refuses_to_pass_off_a_synthetic_fixture_as_a_result(workspace, monkeypatch):
    _run(workspace, monkeypatch=monkeypatch)

    report = (workspace / "evidence" / "report.md").read_text(encoding="utf-8")
    assert "NOT A REPORTED RESULT" in report
    assert "synthetic_scaffold" in report
    assert "## Fixtures behind these numbers" in report


def test_every_gold_signal_would_pass_the_provenance_gate():
    """The gold labels describe cards a perfect system would emit, so they must survive the
    gate. If a tightening ever invalidates the frozen set, this says so on the same commit
    rather than in the results table."""
    from ts.provenance import check_card

    for case in run_eval.load_cases("all"):
        index = run_eval.load_fixture(run_eval.FIXTURES_DIR / case["fixture"])
        gold = run_eval.load_gold(case["case_id"])
        for signal in gold["gold_signals"]:
            card = {"type": signal["type"], "window_ms": case["window_ms"],
                    "evidence": signal["relevant_message_ids"],
                    "trigger": {"event_id": signal["trigger_event_id"]}}
            result = check_card(card, index)
            assert result.ok, f"{case['case_id']}: gold card fails the gate {result.codes}"
