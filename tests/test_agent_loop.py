"""End-to-end proof that the agent LOOP runs offline with a fake provider.

This is what removes the need for a framework: the model chooses tools, the controller executes
them and feeds results back, and a deterministic gate judges the final cards.
"""
import json
from pathlib import Path

from ts.baseline import single_prompt
from ts.cache import ResponseCache
from ts.ingest.replay import load_fixture
from ts.workflow.agent import (MAX_CARDS, MAX_TOOL_CALLS_PER_STEP,
                               AudienceSignalAgent)

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "sample"

GOOD = {"type": "audience_answer", "title": "chat says лес",
        "distribution": {"лес": 7, "база": 5},
        "trigger": {"kind": "speech", "event_id": "tr_0001",
                    "quote": "куда идти - в лес или на базу?"},
        "evidence": ["msg_0001", "msg_0002"], "confidence": 0.9}

HALLUCINATED = {"type": "reaction", "title": "invented",
                "trigger": {"kind": "speech", "event_id": "tr_0001",
                            "quote": "какое оружие мне взять"},
                "evidence": ["msg_0001"], "confidence": 0.9}


def scripted(*replies):
    """Fake provider replaying a fixed script of assistant messages."""
    state = {"i": 0, "seen": []}

    def provider(request):
        state["seen"].append(request)
        i = min(state["i"], len(replies) - 1)
        state["i"] += 1
        return {"choices": [{"message": {"content": json.dumps(replies[i])}}]}

    provider.state = state
    return provider


def test_agent_calls_tools_then_answers(tmp_path):
    """Two model turns: the model asks for context, receives it, then answers."""
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000

    provider = scripted(
        {"action": "call_tools", "why": "need the question and the replies",
         "calls": [{"tool": "get_transcript_window", "start_ms": start, "end_ms": end},
                   {"tool": "group_repeated", "start_ms": start, "end_ms": end}]},
        {"action": "answer", "cards": [GOOD, HALLUCINATED]},
    )
    agent = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"), provider=provider)
    out = agent.run("t1", start, end)

    assert out["steps"] == 2, "the model should take one tool turn then answer"
    assert len(provider.state["seen"]) == 2

    # the second request must actually contain the tool output fed back in
    second = json.dumps(provider.state["seen"][1], ensure_ascii=False)
    assert "TOOL RESULTS" in second and "tr_0001" in second

    assert len(out["verified"]) == 1 and len(out["rejected"]) == 1
    assert out["unsupported_rate"] == 0.5
    assert "E_QUOTE_MISMATCH" in [v["code"] for v in out["rejected"][0]["gate"]["violations"]]
    assert out["verified"][0]["action"] == {"kind": "draft_poll", "state": "pending_approval"}
    assert Path(out["trace_path"]).exists()


def test_trace_records_the_whole_trajectory(tmp_path):
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000
    provider = scripted(
        {"action": "call_tools", "calls": [{"tool": "group_repeated", "start_ms": start, "end_ms": end}]},
        {"action": "answer", "cards": [GOOD]},
    )
    out = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"),
                              provider=provider).run("t2", start, end)
    steps = json.loads(Path(out["trace_path"]).read_text())["steps"]
    kinds = [s["kind"] for s in steps]
    assert "instructions" in kinds and "tool_call" in kinds and "model_call" in kinds
    assert "provenance_gate" in kinds and "human_checkpoint" in kinds and "result" in kinds


def test_controller_rejects_unknown_tool_and_oversized_window(tmp_path):
    """The model never touches the index directly; the controller validates every call."""
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000
    provider = scripted(
        {"action": "call_tools", "calls": [
            {"tool": "delete_everything", "start_ms": start, "end_ms": end},
            {"tool": "group_repeated", "start_ms": start, "end_ms": start + 999_999_999},
        ]},
        {"action": "answer", "cards": [GOOD]},
    )
    out = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"),
                              provider=provider).run("t3", start, end)
    fed_back = json.dumps(provider.state["seen"][1], ensure_ascii=False)
    assert "unknown tool" in fed_back
    assert "exceeds cap" in fed_back
    assert len(out["verified"]) == 1  # the agent still recovers and answers


def test_step_budget_terminates(tmp_path):
    """A model that never answers must not loop forever."""
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000
    provider = scripted({"action": "call_tools",
                         "calls": [{"tool": "group_repeated", "start_ms": start, "end_ms": end}]})
    out = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"),
                              provider=provider).run("t4", start, end, max_steps=3)
    assert out["steps"] == 3 and out["verified"] == []


def test_malformed_json_is_retried_not_fatal(tmp_path):
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000

    replies = [None, {"action": "answer", "cards": [GOOD]}]
    state = {"i": 0}

    def provider(_req):
        i = state["i"]; state["i"] += 1
        content = "not json at all" if replies[min(i, 1)] is None else json.dumps(replies[1])
        return {"choices": [{"message": {"content": content}}]}

    out = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"),
                              provider=provider).run("t5", start, end)
    assert len(out["verified"]) == 1


def test_whole_trajectory_replays_with_no_provider(tmp_path):
    """Every step is its own cache entry, so a multi-turn run reproduces with zero API calls."""
    index = load_fixture(FIXTURE)
    start, end = index.start_ms, index.start_ms + 12_000
    script = (
        {"action": "call_tools", "calls": [{"tool": "group_repeated", "start_ms": start, "end_ms": end}]},
        {"action": "answer", "cards": [GOOD]},
    )
    first = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="record"),
                                provider=scripted(*script)).run("t6", start, end)

    def exploding(_req):
        raise AssertionError("replay mode must never reach the provider")

    second = AudienceSignalAgent(index, ResponseCache(tmp_path, mode="replay"),
                                 provider=exploding).run("t6", start, end)

    assert second["steps"] == first["steps"] == 2
    assert [c["title"] for c in second["verified"]] == [c["title"] for c in first["verified"]]


def test_baseline_scored_through_the_same_gate(tmp_path):
    """The gate is the scorer, not part of the agent's advantage - otherwise it would be rigged."""
    index = load_fixture(FIXTURE)
    bad = {"type": "reaction", "title": "ghost evidence",
           "trigger": {"kind": "unknown", "event_id": "unknown", "quote": None},
           "evidence": ["msg_9999"], "confidence": 0.8}

    def provider(_req):
        return {"choices": [{"message": {"content": json.dumps({"cards": [bad]})}}]}

    out = single_prompt.run(index, ResponseCache(tmp_path, mode="record"), "t7",
                            index.start_ms, index.start_ms + 12_000, provider=provider)
    assert out["unsupported_rate"] == 1.0
    assert "E_UNKNOWN_MSG" in [v["code"] for v in out["rejected"][0]["gate"]["violations"]]


def test_chat_only_ablation_hides_speech_and_frames():
    index = load_fixture(FIXTURE)
    full = single_prompt.render_events(index, index.start_ms, index.end_ms, chat_only=False)
    only = single_prompt.render_events(index, index.start_ms, index.end_ms, chat_only=True)
    assert "SPEECH" in full and "SCREEN" in full
    assert "SPEECH" not in only and "SCREEN" not in only


# --------------------------------------------------------------------------- the caps are real
# The prompt asks for at most three cards. Left there it is a hope: measured before this, a model
# returning ten cards got ten kept, in both systems. The eval promises the baseline "the same
# output schema and card cap", and an unenforced cap contaminates the comparison — a system that
# ignores it gets more chances at recall and more cards to average the unsupported rate over.
def _answer(n, card=None):
    return {"action": "answer",
            "cards": [dict(card or GOOD, title=f"card {i}") for i in range(n)]}


def test_the_card_cap_is_enforced_by_the_controller(tmp_path):
    index = load_fixture(FIXTURE)
    agent = AudienceSignalAgent(index, ResponseCache(tmp_path / "c", mode="record"),
                                provider=scripted(_answer(10)))

    out = agent.run("t", 1756399998000, 1756400010000)

    assert len(out["verified"]) + len(out["rejected"]) == MAX_CARDS
    assert out["cards_dropped_by_cap"] == 7


def test_the_baseline_gets_exactly_the_same_cap(tmp_path):
    """Fairness: the cap has to be applied in one place, to both, or the comparison measures
    obedience to a prompt instead of the workflow."""
    index = load_fixture(FIXTURE)

    out = single_prompt.run(index, ResponseCache(tmp_path / "c", mode="record"),
                            "t", 1756399998000, 1756400010000,
                            provider=scripted(_answer(10)))

    assert len(out["verified"]) + len(out["rejected"]) == MAX_CARDS
    assert out["cards_dropped_by_cap"] == 7


def test_unknown_card_types_are_dropped_before_the_cap_applies(tmp_path):
    """Otherwise five junk cards would fill the cap and squeeze out the real ones."""
    junk = [{"type": "not_a_card_type", "title": f"junk {i}"} for i in range(5)]
    reply = {"action": "answer", "cards": junk + [dict(GOOD, title="real")]}
    index = load_fixture(FIXTURE)

    out = AudienceSignalAgent(index, ResponseCache(tmp_path / "c", mode="record"),
                              provider=scripted(reply)).run("t", 1756399998000, 1756400010000)

    kept = out["verified"] + out["rejected"]
    assert [c["title"] for c in kept] == ["real"]
    assert out["cards_dropped_by_cap"] == 0


def test_a_dropped_card_is_reported_not_silently_removed(tmp_path):
    index = load_fixture(FIXTURE)
    agent = AudienceSignalAgent(index, ResponseCache(tmp_path / "c", mode="record"),
                                provider=scripted(_answer(5)))

    out = agent.run("t", 1756399998000, 1756400010000)

    trace = json.loads(Path(out["trace_path"]).read_text(encoding="utf-8"))
    result = [s for s in trace["steps"] if s["kind"] == "result"][-1]
    assert result["payload"]["cards_dropped_by_cap"] == 2


def test_the_tool_call_cap_names_what_it_dropped(tmp_path):
    calls = [{"tool": "get_chat_window", "start_ms": 1756399998000, "end_ms": 1756400010000}] * 7
    index = load_fixture(FIXTURE)
    agent = AudienceSignalAgent(index, ResponseCache(tmp_path / "c", mode="record"),
                                provider=scripted({"action": "call_tools", "calls": calls},
                                                  _answer(1)))

    out = agent.run("t", 1756399998000, 1756400010000)
    trace = json.loads(Path(out["trace_path"]).read_text(encoding="utf-8"))

    assert sum(1 for s in trace["steps"] if s["kind"] == "tool_call") == MAX_TOOL_CALLS_PER_STEP
