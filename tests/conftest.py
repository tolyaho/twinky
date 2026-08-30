import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# The window of the synthetic `sample` fixture that holds the binary-choice exchange.
STUB_WINDOW = [1756399998000, 1756400010000]


@pytest.fixture
def stub_cases(tmp_path, monkeypatch):
    """A case set owned by the tests, pointing at the synthetic `sample` fixture.

    These tests exercise the eval RUNNER, not whatever is currently frozen in `evals/cases/`.
    They used to read the graded set directly, so freezing the real capture-backed cases broke
    ten tests that have nothing to do with the cases — the harness has to be testable
    independently of the deliverable it happens to be scoring.
    """
    from evals import run_eval

    cases, gold = tmp_path / "stub_cases", tmp_path / "stub_gold"
    cases.mkdir(), gold.mkdir()
    (cases / "c01_binary_choice.json").write_text(json.dumps({
        "case_id": "c01_binary_choice", "fixture": "sample",
        "fixture_kind": "synthetic_scaffold", "window_ms": STUB_WINDOW,
        "description": "Test-owned stub: streamer asks a binary question, chat answers.",
    }), encoding="utf-8")
    (gold / "c01_binary_choice.json").write_text(json.dumps({
        "case_id": "c01_binary_choice", "fixture": "sample", "window_ms": STUB_WINDOW,
        "gold_signals": [{"type": "audience_answer", "trigger_event_id": "tr_0001",
                          "relevant_message_ids": ["msg_0001", "msg_0002", "msg_0003"]}],
        "must_abstain": False, "reviewed": False,
    }), encoding="utf-8")
    monkeypatch.setattr(run_eval, "CASES_DIR", cases)
    monkeypatch.setattr(run_eval, "GOLD_DIR", gold)
    return cases


@pytest.fixture(autouse=True, scope="session")
def _traces_stay_out_of_the_deliverable(tmp_path_factory):
    """`trajectories/` is a graded deliverable: it must hold real runs and nothing else.

    Tests that construct an agent without changing directory wrote there — 55 files with case
    ids no evaluation case has. Redirecting for the whole session fixes the class of problem
    rather than the instances of it.
    """
    import os

    previous = os.environ.get("TS_TRACE_DIR")
    os.environ["TS_TRACE_DIR"] = str(tmp_path_factory.mktemp("trajectories"))
    yield
    if previous is None:
        os.environ.pop("TS_TRACE_DIR", None)
    else:
        os.environ["TS_TRACE_DIR"] = previous


# ---------------------------------------------------------------- source, without the prose
# House rule, learned six times: a guard that greps raw source fires on the comment explaining
# why the forbidden thing is absent. `/* textContent, never innerHTML */` is not a use of
# innerHTML. Assert against code; explain in prose.

def strip_js_comments(source: str) -> str:
    """`/* … */` and `// …` removed, string literals left alone."""
    import re

    out, i, n = [], 0, len(source)
    while i < n:
        two = source[i:i + 2]
        if two == "/*":
            i = source.find("*/", i + 2)
            i = n if i == -1 else i + 2
        elif two == "//":
            end = source.find("\n", i)
            i = n if end == -1 else end
        elif source[i] in "\"'`":
            quote = source[i]
            j = i + 1
            while j < n and source[j] != quote:
                j += 2 if source[j] == "\\" else 1
            out.append(source[i:j + 1])
            i = j + 1
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


@pytest.fixture
def js_source():
    """Read a static JS file with its comments stripped."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src/ts/report/static"

    def read(name: str) -> str:
        return strip_js_comments((root / name).read_text(encoding="utf-8"))

    return read
