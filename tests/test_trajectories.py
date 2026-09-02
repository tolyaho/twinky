"""`trajectories/` is published as reproducible, so it must hold real runs, nothing else, and
the same bytes on every replay.

The suite wrote 55 files into it before `TS_TRACE_DIR` existed, every one with a case id no
evaluation case has. A reviewer opening that directory would have been reading test output.
"""
import json
import os
import re
from pathlib import Path

import pytest

from ts.workflow.trace import DEFAULT_TRACE_DIR, Trace, trace_dir

REPO = Path(__file__).resolve().parents[1]
PRODUCT_AGENT = REPO / "trajectories" / "product-agent"

# A real case id is either a frozen eval case (`c07_something`) or a tiled replay window
# (`<fixture_id>_w03`). Anything else came from a test.
REAL_CASE_ID = re.compile(r"^(c\d{2}_[a-z0-9_]+|[A-Za-z0-9._-]+_w\d{2,})$")


def test_the_deliverable_holds_no_test_output():
    stray = []
    for path in PRODUCT_AGENT.glob("*.json"):
        case_id = json.loads(path.read_text(encoding="utf-8")).get("case_id", "")
        if not REAL_CASE_ID.match(case_id):
            stray.append(f"{path.name} (case_id={case_id!r})")

    assert not stray, f"test output in a graded deliverable: {stray}"


def test_traces_are_redirectable_so_the_suite_cannot_pollute_it(tmp_path, monkeypatch):
    monkeypatch.setenv("TS_TRACE_DIR", str(tmp_path / "elsewhere"))

    written = Trace(agent="audience_signal_agent", case_id="c01_binary_choice").write()

    assert written.parent == tmp_path / "elsewhere"
    assert not (PRODUCT_AGENT / written.name).exists()


def test_the_default_is_still_the_deliverable_directory(monkeypatch):
    """The redirect is for tests and tooling; a real run must land in the deliverable."""
    monkeypatch.delenv("TS_TRACE_DIR", raising=False)

    assert trace_dir() == Path(DEFAULT_TRACE_DIR) == Path("trajectories/product-agent")


def test_the_suite_itself_is_redirected():
    """Autouse session fixture in conftest. If this ever fails, every test run is quietly
    writing into the deliverable again."""
    assert os.environ.get("TS_TRACE_DIR")
    assert Path(os.environ["TS_TRACE_DIR"]).resolve() != PRODUCT_AGENT.resolve()


@pytest.mark.parametrize("agent", ["audience_signal_agent", "baseline_single_prompt",
                                   "baseline_chat_only"])
def test_the_readme_names_every_system_that_owes_a_trajectory(agent):
    """Three systems are compared, so three trajectories are required. The README must say so
    while they are still missing, not quietly list only the one that exists."""
    readme = (REPO / "trajectories" / "README.md").read_text(encoding="utf-8")

    assert agent in readme


def test_the_coding_agent_disclosure_is_filled_in():
    disclosure = (REPO / "trajectories" / "coding-agents" / "README.md").read_text(
        encoding="utf-8")

    assert "Claude Code" in disclosure
    assert "2.1.246" in disclosure           # a version, not a bare tool name
    assert "<!-- TODO -->" not in disclosure


# ------------------------------------------------------------------ at_ms determinism (RISKS #54)
def test_a_replay_trace_records_no_wall_clock_timing(tmp_path, monkeypatch):
    """`perf_counter` resolved a cached lookup as 0 ms on one run and 1 ms on the next, so one
    frozen-case trajectory changed on every `make eval` — in a directory documented as
    reproducible. Same defect as the uuid4 trace id, one field over."""
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    t = Trace("agent", "c01_case", out_dir=tmp_path)
    t.instructions("sys", "usr")
    t.tool_call("get_chat_window", {}, {"n": 3})
    t.result({"cards": []})

    assert [s["at_ms"] for s in t.steps] == [None, None, None]


def test_a_recorded_trace_keeps_its_real_latencies(tmp_path, monkeypatch):
    """Record mode talks to a live provider, so the numbers are real and are the only latency
    data the project has. 45 committed trajectories carry them."""
    monkeypatch.setenv("TS_LLM_MODE", "record")

    t = Trace("agent", "c01_case", out_dir=tmp_path)
    t.instructions("sys", "usr")

    assert all(isinstance(s["at_ms"], int) for s in t.steps)


def test_two_replays_of_one_case_write_identical_bytes(tmp_path, monkeypatch):
    """The property the trajectories directory claims. Asserted end to end rather than inferred
    from the field, because the trace id and the step payloads have to hold still too."""
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    written = []
    for run in ("a", "b"):
        out = tmp_path / run
        t = Trace("agent", "c01_case", out_dir=out)
        t.instructions("sys", "usr")
        t.tool_call("get_chat_window", {"window_ms": [0, 60000]}, {"n": 3})
        t.gate("sig_1", True, [])
        t.result({"cards": []})
        written.append(t.write().read_bytes())

    assert written[0] == written[1]
