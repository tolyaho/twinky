import pytest
from ts.cache import CacheMiss, ResponseCache, request_hash


def test_hash_is_key_order_independent():
    a = {"model": "m", "temperature": 0.0, "messages": [{"role": "u", "content": "hi"}]}
    b = {"messages": [{"role": "u", "content": "hi"}], "temperature": 0.0, "model": "m"}
    assert request_hash(a) == request_hash(b)


def test_hash_changes_with_temperature():
    a = {"model": "m", "temperature": 0.0}
    b = {"model": "m", "temperature": 0.2}
    assert request_hash(a) != request_hash(b)


def test_replay_miss_raises_and_never_calls_provider(tmp_path):
    calls = []
    def provider(req):
        calls.append(req)
        return {"choices": []}
    c = ResponseCache(tmp_path, mode="replay")
    with pytest.raises(CacheMiss):
        c.call({"model": "m", "temperature": 0.0}, provider)
    assert calls == [], "replay mode must never reach the provider"


def test_record_then_replay_reproduces_exactly(tmp_path):
    req = {"model": "m", "temperature": 0.0, "messages": [{"role": "u", "content": "hi"}]}
    n = {"i": 0}
    def provider(_):
        n["i"] += 1
        return {"choices": [{"message": {"content": f"resp-{n['i']}"}}]}

    rec = ResponseCache(tmp_path, mode="record")
    first = rec.call(req, provider)

    rep = ResponseCache(tmp_path, mode="replay")
    second = rep.call(req, provider)

    assert first == second
    assert n["i"] == 1, "replay must not re-call the provider"
    assert rep.stats()["hits"] == 1


def test_live_mode_bypasses_cache(tmp_path):
    n = {"i": 0}
    def provider(_):
        n["i"] += 1
        return {"n": n["i"]}
    c = ResponseCache(tmp_path, mode="live")
    assert c.call({"model": "m"}, provider) == {"n": 1}
    assert c.call({"model": "m"}, provider) == {"n": 2}


def test_unknown_mode_rejected(tmp_path):
    with pytest.raises(ValueError):
        ResponseCache(tmp_path, mode="whatever")
