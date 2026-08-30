"""The measurement plumbing, guarded at the two places it silently broke.

The first measured run produced `baseline: 11 cases, 0 cards` and `agent: unsupported 0.95`, and
the eval printed both as results. Neither was a quality finding:

  1. The baseline was handed the AGENT's system prompt, which specifies a tool-calling protocol.
     Having no tools, the model replied `{"action": "call_tools", ...}` — correctly — and
     `.get("cards", [])` turned that into a clean empty list with no error raised.
  2. 19 of the agent's 20 cards were rejected on E_CIRCULAR_EVIDENCE alone, because the prompt
     documented `trigger.event_id` without ever saying it must be a speech or screen event and
     must not appear in the card's own evidence. The gate enforced a rule the prompt never
     stated.

Both are silent-success failures: the run completes, the table fills, and the numbers mean
nothing. That class has now cost this project four times (iterations 8, 13, the enrich guard,
and this).
"""
import json

import pytest

from evals import run_eval
from ts.baseline import single_prompt
from ts.events import Event, EventIndex
from ts.workflow import agent


# --------------------------------------------------------------- prompt symmetry
def test_both_systems_share_one_card_contract():
    """The eval promises the baseline 'the same output schema and card cap'. Two hand-kept
    copies would drift, and a drifted contract measures as a difference the workflow did not
    earn. One string, included verbatim by both."""
    assert agent.CARD_CONTRACT in agent.SYSTEM
    assert agent.CARD_CONTRACT in single_prompt.SYSTEM


def test_the_baseline_is_not_given_the_tool_protocol():
    """The exact defect: the baseline cannot call a tool, so telling it it may is an instruction
    to produce a reply the baseline parser then throws away."""
    assert "call_tools" not in single_prompt.SYSTEM
    assert agent.TOOLS_DOC not in single_prompt.SYSTEM
    assert "group_repeated" not in single_prompt.SYSTEM
    # ...while the agent still has it.
    assert "call_tools" in agent.SYSTEM


def test_the_agent_keeps_the_only_permitted_asymmetry():
    assert agent.TOOLS_DOC in agent.SYSTEM


@pytest.mark.parametrize("system_prompt", [agent.SYSTEM, single_prompt.SYSTEM])
def test_the_trigger_rule_the_gate_enforces_is_stated_to_both(system_prompt):
    """E_CIRCULAR_EVIDENCE and E_EVIDENCE_NOT_A_MESSAGE were unstated rules. A scorer may not
    penalise a constraint the contract never expressed."""
    assert "never a chat id" in system_prompt.lower()
    assert "cannot be its own cause" in system_prompt
    assert "unknown" in system_prompt


@pytest.mark.parametrize("system_prompt", [agent.SYSTEM, single_prompt.SYSTEM])
def test_both_prompts_state_the_same_card_cap(system_prompt):
    assert f"At most {agent.MAX_CARDS} cards" in system_prompt


# --------------------------------------------------------------- the silent zero
def index():
    return EventIndex([
        Event(event_id="msg_1", type="chat_message", ts_ms=1000, payload={"text": "lol"}),
        Event(event_id="tr_1", type="transcript_segment", ts_ms=900, payload={"text": "i died"}),
    ])


def reply(payload):
    def provider(_request):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}
    return provider


@pytest.fixture
def cache(tmp_path, monkeypatch):
    from ts.cache import ResponseCache
    monkeypatch.setenv("TS_LLM_MODE", "record")
    return ResponseCache(cache_dir=tmp_path / "cache")


def test_a_tool_call_reply_is_reported_as_a_failure_not_an_empty_result(cache):
    """The regression. Before the fix this returned zero cards and no error, which is how
    eleven cases reported a clean zero."""
    out = single_prompt.run(index(), cache, "c_test", 0, 2000,
                            provider=reply({"action": "call_tools", "calls": []}))

    assert out["parse_error"], "a reply with no 'cards' key must be recorded as a failure"
    assert "cards" in out["parse_error"]
    assert out["total"] == 0


def test_a_genuinely_empty_answer_is_not_reported_as_a_failure(cache):
    """The other side of it: `{"cards": []}` is a real, if unhelpful, answer. Conflating the two
    would make the new guard fire on correct behaviour."""
    out = single_prompt.run(index(), cache, "c_test", 0, 2000, provider=reply({"cards": []}))

    assert out["parse_error"] is None
    assert out["total"] == 0


def test_a_bare_list_reply_is_reported_as_a_failure(cache):
    out = single_prompt.run(index(), cache, "c_test", 0, 2000, provider=reply([{"type": "none"}]))

    assert out["parse_error"]


def test_a_well_formed_answer_still_produces_cards(cache):
    out = single_prompt.run(index(), cache, "c_test", 0, 2000, provider=reply({"cards": [
        {"type": "reaction", "title": "laughter", "evidence": ["msg_1"],
         "trigger": {"kind": "speech", "event_id": "tr_1", "quote": "i died"}}]}))

    assert out["parse_error"] is None
    assert out["total"] == 1
    assert len(out["verified"]) == 1, out["rejected"]


# --------------------------------------------------------------- the eval-level guard
def test_the_report_brands_a_system_that_emitted_nothing(tmp_path):
    """`trigger_accuracy: null` reads as 'not computed yet'. It has to read as 'broken'."""
    from evals.scorer import CaseScore

    dead = CaseScore(case_id="c1", system="baseline", n_cards=0, n_gold=1, trigger_correct=0,
                     trigger_scored=0, unmatched=0, unsupported=0, signal_recall_hits=0,
                     abstain_expected=False, abstain_correct=None)
    live = CaseScore(case_id="c1", system="agent", n_cards=2, n_gold=1, trigger_correct=1,
                     trigger_scored=1, unmatched=1, unsupported=0, signal_recall_hits=1,
                     abstain_expected=False, abstain_correct=None)

    run_eval.write_outputs([dead, live], tmp_path,
                           {"fx": {"kind": "capture", "channel": "c", "provenance": "p",
                                   "cases": ["c1"]}})
    report = (tmp_path / "report.md").read_text(encoding="utf-8")

    assert "BROKEN — NOT A RESULT" in report
    assert "baseline" in report.split("BROKEN")[1][:200]


def test_the_report_says_nothing_when_every_system_answered(tmp_path):
    from evals.scorer import CaseScore

    live = CaseScore(case_id="c1", system="agent", n_cards=2, n_gold=1, trigger_correct=1,
                     trigger_scored=1, unmatched=1, unsupported=0, signal_recall_hits=1,
                     abstain_expected=False, abstain_correct=None)

    run_eval.write_outputs([live], tmp_path,
                           {"fx": {"kind": "capture", "channel": "c", "provenance": "p",
                                   "cases": ["c1"]}})

    assert "BROKEN" not in (tmp_path / "report.md").read_text(encoding="utf-8")


# --------------------------------------------------------------- citable ids
def test_every_rendered_line_labels_the_id_it_must_be_cited_by():
    """The second silent failure of the first measured run: the format led with a bare
    bracketed timestamp, so every system cited that number as the id and was rejected on
    E_UNKNOWN_MSG. Nothing could match gold or clear the gate."""
    ix = EventIndex([
        Event(event_id="msg_a", type="chat_message", ts_ms=1500,
              payload={"text": "amethyst", "author": "u_1"}),
        Event(event_id="tr_a", type="transcript_segment", ts_ms=1100,
              payload={"text": "i died", "speaker": "spk_0"}),
        Event(event_id="frm_a", type="frame_caption", ts_ms=1000, payload={"text": "a screen"}),
    ])

    rendered = single_prompt.render_events(ix, 0, 2000)

    for line in rendered.splitlines():
        assert "id=" in line, line
        # the timestamp must never be the first token, where it reads as the identifier
        assert not line.startswith("["), line
    assert "id=msg_a" in rendered and "id=tr_a" in rendered and "id=frm_a" in rendered


def test_the_baseline_is_told_which_token_is_the_id():
    assert "id=" in single_prompt.SYSTEM
    assert "never an id" in single_prompt.SYSTEM


# --------------------------------------------------------------- keyless reproduction
def test_the_default_model_is_the_one_the_cache_was_recorded_with():
    """Reproducibility is a pre-scoring gate, and the model name is part of the cache key.

    While the default was a model no run had ever been recorded with, `make eval` reproduced
    only for someone whose environment set TS_TEXT_MODEL — which is the author and nobody else.
    A judge's fresh clone missed every entry and exited 3. The env var stays as the re-record
    override; the default has to be what is actually in `cache/`.
    """
    import glob
    import json as _json
    from pathlib import Path

    recorded = set()
    root = Path(__file__).resolve().parents[1]
    for p in glob.glob(str(root / "cache" / "llm" / "*" / "*")):
        req = _json.loads(Path(p).read_text(encoding="utf-8")).get("request") or {}
        if req.get("messages"):
            recorded.add(req.get("model"))

    if not recorded:
        pytest.skip("no text responses recorded yet")
    assert agent.DEFAULT_TEXT_MODEL in recorded, (
        f"default {agent.DEFAULT_TEXT_MODEL!r} was never recorded; cache holds {recorded}")
    assert single_prompt.DEFAULT_TEXT_MODEL == agent.DEFAULT_TEXT_MODEL
