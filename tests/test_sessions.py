"""Offline API contract + real cached agent/gate, not predetermined live results."""
import json
from pathlib import Path
import threading
import time
import httpx
import pytest
from ts.cache import ResponseCache
from ts.ingest.replay import load_fixture
from ts.live_limits import LimitedCache, QuotaExceeded
from ts.live_worker import process
from ts.report.serve import make_server
from ts.sessions import AdmissionError, Config, SessionManager
from ts.twitch import TwitchStatus, TwitchUnavailable

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "offline-integration-test-credential-only"


def config(**kwargs):
    return Config(enabled=True, token=TOKEN, starts=4, **kwargs)


def helix(state="live"):
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/users"):
            return {"data": [] if state == "not_found" else [{"id": "fixture-user"}]}
        return {"data": [{}] if state == "live" else []}
    return TwitchStatus("test-client", access_token="test-only", transport=request), calls


def wait(job):
    assert job.done.wait(10), "worker did not complete"


@pytest.mark.parametrize("state", ["live", "offline", "not_found"])
def test_helix_uses_official_users_then_streams_and_distinguishes_missing(state):
    twitch, calls = helix(state)
    result = twitch.lookup("Example_Channel")
    assert result["channel"] == "example_channel" and result["state"] == state
    assert calls[0][1] == "https://api.twitch.tv/helix/users"
    assert calls[0][2]["params"] == {"login": "example_channel"}
    if state != "not_found":
        assert calls[1][2]["params"] == {"user_id": "fixture-user"}


def test_status_provider_failure_never_exposes_secrets():
    def broken(*a, **kw):
        raise ValueError("secret-in-upstream-url")
    with pytest.raises(TwitchUnavailable) as exc:
        TwitchStatus("client", access_token="private", transport=broken).lookup("channel")
    assert "secret" not in str(exc.value) and "private" not in str(exc.value)


def test_api_simulated_live_runs_real_agent_and_supports_sse_cursor():
    twitch, _ = helix()
    from evals.run_eval import load_cases
    case = next(c for c in load_cases() if c["case_id"].startswith("c07"))
    cache = ResponseCache(mode="replay")
    def actual(job, emit):
        index = load_fixture(ROOT / "evals/fixtures" / case["fixture"])
        return process(index, cache, emit, case_id=case["case_id"],
                       start_ms=case["window_ms"][0], end_ms=case["window_ms"][1])
    manager = SessionManager(config(), lookup=twitch.lookup, processor=actual,
                             source_mode="recorded_fixture_test")
    fixture = ROOT / "evals/fixtures" / case["fixture"]
    server = make_server(fixture, ROOT / "evidence/raw-results", 0, quiet=True, sessions=manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
                          headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15) as client:
            assert client.post("/api/sessions", json={"channel": "name", "duration_seconds": 600}).status_code == 400
            response = client.post("/api/sessions", json={"channel": "name"})
            assert response.status_code == 202
            session_id = response.json()["session_id"]
            job = manager.get(session_id)
            wait(job)
            snapshot = client.get(f"/api/sessions/{session_id}").json()
            assert snapshot["state"] == "completed"
            assert snapshot["source_mode"] == "recorded_fixture_test"
            assert snapshot["result"]["cards"] and cache.hits > 0 and cache.misses == 0
            events = client.get(f"/api/sessions/{session_id}/events").text
            envelopes = [json.loads(line[6:]) for line in events.splitlines() if line.startswith("data: ")]
            kinds = {e["type"] for e in envelopes}
            assert {"status", "progress", "context", "candidate_signal", "provenance_decision", "completion"} <= kinds
            assert [e["seq"] for e in envelopes] == list(range(1, len(envelopes)+1))
            assert all(e["schema_version"] == 1 for e in envelopes)
            cursor = envelopes[-2]["seq"]
            tail = client.get(f"/api/sessions/{session_id}/events", headers={"Last-Event-ID": str(cursor)}).text
            assert tail.count("data: ") == 1 and "event: completion" in tail
            assert "withheld pending rights/privacy review" in events
            assert client.get("/api/live?channel=name").status_code == 410
            assert client.get(f"/api/sessions/{session_id}", headers={"Authorization": ""}).status_code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("state", ["offline", "not_found"])
def test_offline_never_invokes_processor(state):
    twitch, _ = helix(state)
    def forbidden(*a):
        pytest.fail("offline channel reached paid worker")
    manager = SessionManager(config(), lookup=twitch.lookup, processor=forbidden)
    job = manager.start("name", "127.0.0.1")
    wait(job)
    assert job.state == state and job.events[-1]["type"] == "completion"


def test_cancellation_holds_capacity_until_processor_cleanup():
    started, cleaned = threading.Event(), threading.Event()
    def work(job, emit):
        started.set()
        job.cancel.wait(5)
        cleaned.set()
        raise InterruptedError()
    manager = SessionManager(config(), lookup=lambda c: {"live": True}, processor=work)
    first = manager.start("name", "127.0.0.1")
    assert started.wait(2)
    with pytest.raises(AdmissionError, match="capacity"):
        manager.start("other", "127.0.0.1")
    first.cancel.set()
    wait(first)
    assert cleaned.is_set() and first.state == "cancelled" and manager._active == 0


@pytest.mark.parametrize("exception,state", [(TimeoutError, "timed_out"), (RuntimeError, "failed"),
                                            (TwitchUnavailable, "unavailable")])
def test_terminal_errors_are_safe_and_capacity_is_released(exception, state):
    def fail(*args):
        raise exception("private upstream details")
    manager = SessionManager(config(), lookup=fail)
    job = manager.start("name", "127.0.0.1")
    wait(job)
    assert job.state == state and manager._active == 0
    assert "private" not in json.dumps(job.events)


def test_fail_closed_auth_rate_and_startup_reservation():
    manager = SessionManager()
    with pytest.raises(AdmissionError, match="not_configured"):
        manager.authorize(None, "127.0.0.1")
    manager = SessionManager(config(), lookup=lambda c: {"state": "offline", "live": False})
    with pytest.raises(AdmissionError, match="ip_not_allowed"):
        manager.authorize(f"Bearer {TOKEN}", "203.0.113.1")
    for _ in range(2):
        wait(manager.start("name", "127.0.0.1"))
    with pytest.raises(AdmissionError, match="ip_rate_limit"):
        manager.start("name", "127.0.0.1")
    assert manager._used == 2


def test_provider_limits_reserve_before_invocation_and_reject_large_context(tmp_path):
    cache = LimitedCache(tmp_path, mode="live")
    called = []
    def provider(request):
        called.append(True)
        return {}
    for _ in range(4):
        cache.call({"max_tokens": 900, "messages": []}, provider)
    with pytest.raises(QuotaExceeded):
        cache.call({"max_tokens": 900, "messages": []}, provider)
    assert len(called) == 4
    fresh = LimitedCache(tmp_path, mode="live")
    with pytest.raises(QuotaExceeded):
        fresh.call({"max_tokens": 900, "messages": ["x" * 40_000]}, provider)
    assert fresh.calls == 0

@pytest.mark.parametrize("cancel", [True, False])
def test_real_worker_process_group_is_stopped_and_private_directory_removed(tmp_path, monkeypatch, cancel):
    """Exercise watchdog/cleanup using an actual process and child, without any network."""
    import dataclasses
    import os
    import subprocess
    from ts import sessions
    for name in ("TS_LLM_API_KEY", "DEEPGRAM_API_KEY"):
        monkeypatch.setenv(name, "offline-test-placeholder")
    monkeypatch.setenv("TS_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(sessions, "LIMITS", dataclasses.replace(sessions.LIMITS, session_seconds=1))
    original = subprocess.Popen
    launched = []
    def spawn(args, **kwargs):
        script = ("import json,subprocess,sys,time; "
                  "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                  "print(json.dumps({'type':'progress','data':{'phase':'test'}}),flush=True); "
                  "time.sleep(60)")
        proc = original([args[0], "-c", script], **kwargs)
        launched.append((proc, Path(kwargs["cwd"])))
        return proc
    monkeypatch.setattr(sessions.subprocess, "Popen", spawn)
    manager = SessionManager(config())
    job = manager.start("name", "127.0.0.1")
    until = time.monotonic() + 3
    while not launched and time.monotonic() < until:
        time.sleep(.01)
    assert launched
    if cancel:
        job.cancel.set()
    wait(job)
    assert job.state == ("cancelled" if cancel else "timed_out")
    proc, scratch = launched[0]
    assert proc.poll() is not None and not scratch.exists()
    with pytest.raises(ProcessLookupError):
        os.killpg(proc.pid, 0)
