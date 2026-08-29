"""CLI wiring on the shipped sample fixture, with the provider faked.

These tests exercise the real command path - argparse, tiling, agent/baseline, provenance gate,
output document - and then prove the property the submission rests on: once recorded, the same
command reproduces the same file in replay mode with the provider unplugged.
"""
import json
import shutil
from pathlib import Path

import pytest

from ts import cli
from ts.report import serve as serve_mod

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"

# Cites real ids from the sample fixture, so the card clears the provenance gate.
ANSWER = {
    "action": "answer",
    "cards": [{
        "type": "audience_answer",
        "title": "Chat says лес",
        "distribution": {"лес": 2, "база": 1},
        "trigger": {"kind": "speech", "event_id": "tr_0001",
                    "quote": "в лес или на базу?"},
        "evidence": ["msg_0001"],
        "confidence": 0.86,
    }],
}


class FakeDeepSeek:
    """Stands in for `providers.base.DeepSeekProvider`. Counts calls so a replay run can be
    asserted to make none."""

    calls = 0

    def __init__(self, *a, **kw):
        pass

    def complete(self, request):
        type(self).calls += 1
        return {"choices": [{"message": {"content": json.dumps(ANSWER, ensure_ascii=False)}}]}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A throwaway copy of the sample fixture. The real `evals/fixtures/` is never written to -
    fixtures are expensive and irreplaceable."""
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ts.providers.base.DeepSeekProvider", FakeDeepSeek)
    FakeDeepSeek.calls = 0
    return tmp_path


def _replay_doc(tmp_path, system="agent"):
    return json.loads((tmp_path / "out" / f"sample.{system}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- window tiling
def test_windows_tile_the_whole_span():
    assert cli.windows(1000, 4000, 1000) == [(1000, 2000), (2000, 3000), (3000, 4000)]


def test_last_window_is_clamped_to_the_span():
    assert cli.windows(0, 2500, 1000)[-1] == (2000, 2500)


def test_a_zero_length_span_still_produces_one_window():
    assert cli.windows(500, 500, 1000) == [(500, 1500)]


def test_window_size_must_be_positive():
    with pytest.raises(ValueError):
        cli.windows(0, 10, 0)


# --------------------------------------------------------------------------- replay / baseline
def test_replay_writes_a_result_document(workspace, monkeypatch):
    monkeypatch.setenv("TS_LLM_MODE", "record")
    monkeypatch.setenv("TS_TRACE_DIR", str(workspace / "trajectories" / "product-agent"))

    rc = cli.main(["replay", "--fixture", "fixture", "--out", "out"])

    assert rc == 0
    doc = _replay_doc(workspace)
    assert doc["system"] == "agent"
    assert doc["fixture_id"] == "sample"
    assert doc["counts"]["windows"] == len(doc["windows"]) == 1
    assert doc["counts"]["verified"] == 1 and doc["counts"]["rejected"] == 0
    card = doc["windows"][0]["verified"][0]
    assert card["trigger"]["event_id"] == "tr_0001"
    assert card["action"] == {"kind": "draft_poll", "state": "pending_approval"}
    # a trajectory is written as the work happens, not reconstructed afterwards
    assert Path(card["trace_id"]) or card["trace_id"]
    assert list((workspace / "trajectories" / "product-agent").glob("*.json"))


def test_baseline_and_ablation_write_separate_documents(workspace, monkeypatch):
    monkeypatch.setenv("TS_LLM_MODE", "record")

    assert cli.main(["baseline", "--fixture", "fixture", "--out", "out"]) == 0
    assert cli.main(["baseline", "--fixture", "fixture", "--out", "out", "--chat-only"]) == 0

    assert _replay_doc(workspace, "baseline")["system"] == "baseline"
    assert _replay_doc(workspace, "ablation_chat_only")["system"] == "ablation_chat_only"


def test_both_systems_see_identical_windows(workspace, monkeypatch):
    """A fairness requirement: anything differing between the two paths other than the system
    itself would show up in the eval as an improvement it did not earn."""
    monkeypatch.setenv("TS_LLM_MODE", "record")
    cli.main(["replay", "--fixture", "fixture", "--out", "out"])
    cli.main(["baseline", "--fixture", "fixture", "--out", "out"])

    agent, baseline = _replay_doc(workspace), _replay_doc(workspace, "baseline")
    assert [w["window_ms"] for w in agent["windows"]] == \
           [w["window_ms"] for w in baseline["windows"]]


def test_recorded_run_replays_with_the_provider_unplugged(workspace, monkeypatch):
    monkeypatch.setenv("TS_LLM_MODE", "record")
    cli.main(["replay", "--fixture", "fixture", "--out", "out"])
    recorded = _replay_doc(workspace)
    calls_after_record = FakeDeepSeek.calls
    assert calls_after_record > 0

    monkeypatch.setenv("TS_LLM_MODE", "replay")
    assert cli.main(["replay", "--fixture", "fixture", "--out", "out"]) == 0

    replayed = _replay_doc(workspace)
    assert FakeDeepSeek.calls == calls_after_record  # no provider call in replay mode
    assert replayed["cache"] == {"hits": 1, "misses": 0}
    # the whole analysis is identical, ids included - this is what REPRODUCTION.md claims
    assert replayed["windows"] == recorded["windows"]


def test_replay_without_a_recording_exits_with_an_actionable_error(workspace, monkeypatch,
                                                                   capsys):
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    rc = cli.main(["replay", "--fixture", "fixture", "--out", "out"])

    assert rc == 3
    assert "TS_LLM_MODE=record" in capsys.readouterr().err
    assert FakeDeepSeek.calls == 0  # a miss must never fall through to a paid call


# --------------------------------------------------------------------------- serve
def test_payload_pairs_fixture_meta_with_the_recorded_run(workspace, monkeypatch):
    monkeypatch.setenv("TS_LLM_MODE", "record")
    cli.main(["replay", "--fixture", "fixture", "--out", "out"])

    got = serve_mod.payload(workspace / "fixture", workspace / "out")

    assert got["meta"]["fixture_id"] == "sample"
    assert got["result"]["counts"]["verified"] == 1


def test_serving_before_a_replay_says_which_command_to_run(workspace):
    with pytest.raises(FileNotFoundError, match="make replay"):
        serve_mod.payload(workspace / "fixture", workspace / "out")


def test_static_route_cannot_escape_the_static_directory():
    assert serve_mod._static_file("../../cli.py") is None


def test_placeholder_page_does_not_pretend_to_be_the_dashboard():
    assert "not the dashboard" in serve_mod.PLACEHOLDER


def test_trace_ids_are_derived_not_random():
    from ts.workflow.trace import make_trace_id

    assert make_trace_id("audience_signal_agent", "sample_w00") == \
           make_trace_id("audience_signal_agent", "sample_w00")
    assert make_trace_id("audience_signal_agent", "sample_w00") != \
           make_trace_id("baseline_single_prompt", "sample_w00")
