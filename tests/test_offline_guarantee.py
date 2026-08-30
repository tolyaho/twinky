"""C2 rehearsal: the graded chain must run with no keys and no network.

The real C2 needs recorded fixtures and waits on RISKS #2. What does not wait is the property
C2 exists to prove — that `baseline`, `replay` and `eval` neither read a credential they need
nor open a socket. That is checkable today on the scaffold fixture, and checking it by executing
the commands is worth more than reading the code and concluding it looks fine.

The chain is run twice: once in `record` mode against a fake provider to populate a cache, then
in `replay` mode with every credential stripped from the environment and the socket constructor
booby-trapped.
"""
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from evals import run_eval
from ts import cli

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"

CREDENTIAL_VARS = ["DEEPSEEK_API_KEY", "DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY",
                   "OPENAI_API_KEY", "LLM_API_KEY", "USER_ACCESS_TOKEN", "DB_PASSWORD"]

ANSWER = {
    "action": "answer",
    "cards": [{
        "type": "audience_answer", "title": "Chat says лес",
        "distribution": {"лес": 9, "база": 6},
        "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
        "evidence": ["msg_0001", "msg_0002"], "confidence": 0.86,
    }],
}


class FakeDeepSeek:
    def __init__(self, *a, **kw):
        pass

    def complete(self, request):
        return {"choices": [{"message": {"content": json.dumps(ANSWER, ensure_ascii=False)}}]}


class NetworkUsed(AssertionError):
    pass


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """A workspace with no credentials in the environment and no working socket."""
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TS_TRACE_DIR", str(tmp_path / "trajectories"))
    for var in CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    return tmp_path


@pytest.fixture
def no_network(monkeypatch):
    def explode(*a, **kw):
        raise NetworkUsed("a graded command opened a socket in replay mode")

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(socket, "getaddrinfo", explode)


def _record(monkeypatch):
    """Populate the cache through the real code path, with the provider faked.

    The fake is installed and removed around this call only. Everything after it runs against
    the real `DeepSeekProvider` class, so a replay that tried to call out would actually try.
    """
    import ts.providers.base as base

    monkeypatch.setenv("TS_LLM_MODE", "record")
    real = base.DeepSeekProvider
    base.DeepSeekProvider = FakeDeepSeek
    try:
        cli.main(["replay", "--fixture", "fixture", "--out", "out"])
        cli.main(["baseline", "--fixture", "fixture", "--out", "out"])
        run_eval.main(["--cases", "c01_binary_choice", "--out", "evidence"])
    finally:
        base.DeepSeekProvider = real


def test_the_whole_chain_replays_with_no_keys_and_no_socket(offline, monkeypatch, no_network):
    """`make baseline && make replay && make eval`, which is C2's command list, run with every
    credential removed and the socket constructor booby-trapped."""
    _record(monkeypatch)
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    assert cli.main(["replay", "--fixture", "fixture", "--out", "out"]) == 0
    assert cli.main(["baseline", "--fixture", "fixture", "--out", "out"]) == 0
    assert run_eval.main(["--cases", "c01_binary_choice", "--out", "evidence"]) == 0

    doc = json.loads((offline / "out" / "sample.agent.json").read_text(encoding="utf-8"))
    assert doc["cache"] == {"hits": 1, "misses": 0}
    assert (offline / "evidence" / "comparison.csv").exists()


def test_an_unrecorded_system_still_fails_loudly_rather_than_calling_out(offline, monkeypatch,
                                                                        no_network):
    """The ablation was never recorded. It must miss, not quietly reach for a provider."""
    _record(monkeypatch)
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    assert cli.main(["baseline", "--fixture", "fixture", "--out", "out", "--chat-only"]) == 3


def test_replay_produces_the_same_document_with_and_without_credentials(offline, monkeypatch):
    _record(monkeypatch)
    with_keys = (offline / "out" / "sample.agent.json").read_text(encoding="utf-8")

    monkeypatch.setenv("TS_LLM_MODE", "replay")
    for var in CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    cli.main(["replay", "--fixture", "fixture", "--out", "out"])

    replayed = (offline / "out" / "sample.agent.json").read_text(encoding="utf-8")
    assert json.loads(replayed)["windows"] == json.loads(with_keys)["windows"]


def test_the_debrief_and_dashboard_payload_need_nothing(offline, monkeypatch, no_network):
    _record(monkeypatch)
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    assert cli.main(["debrief", "--fixture", "fixture", "--out", "out"]) == 0
    assert (offline / "out" / "sample.debrief.md").exists()

    from ts.report.serve import payload
    assert payload(offline / "fixture", offline / "out")["result"]["counts"]["verified"] == 1


def test_an_empty_cache_fails_loudly_instead_of_reaching_for_a_key(offline, monkeypatch,
                                                                  no_network, capsys):
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    assert cli.main(["replay", "--fixture", "fixture", "--out", "out"]) == 3

    err = capsys.readouterr().err
    assert "TS_LLM_MODE=record" in err
    assert "DEEPSEEK_API_KEY" not in err   # a miss is a miss, not a missing-key error


# --------------------------------------------------------------------------- out of process
def test_a_replay_run_never_imports_the_network_stack():
    """`httpx` is imported lazily inside the provider. If it appears in a replay run's module
    table, something on the graded path is preparing to make a request."""
    script = (
        "import sys, runpy;"
        "sys.argv = ['ts.cli', 'inspect', '--fixture', 'evals/fixtures/sample'];"
        "runpy.run_module('ts.cli', run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script + ";" + "assert 'httpx' not in sys.modules"],
        cwd=REPO, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "TS_LLM_MODE": "replay",
             "PYTHONPATH": str(REPO / "src")},
    )

    assert result.returncode == 0, result.stderr[-800:]


def test_the_cli_runs_with_the_environment_stripped_to_nothing():
    """No `.env`, no keys, not even a full PATH — C2's actual precondition."""
    result = subprocess.run(
        [sys.executable, "-m", "ts.cli", "inspect", "--fixture", "evals/fixtures/sample"],
        cwd=REPO, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONPATH": str(REPO / "src")},
    )

    assert result.returncode == 0, result.stderr[-800:]
    assert json.loads(result.stdout)["events"] == 36
