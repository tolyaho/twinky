"""The grounded arm: the window's speech and screen events, inlined in the model's turn.

Diagnosed in iteration 55 from the recorded cache. The contract demands a SPEECH or SCREEN id and
swears the model may only cite ids it "actually saw in the input" — and all 57 of the agent's own
recorded openings contain zero event ids. Across the 70 conversations that reached a tool result,
chat appeared in 70 and frame captions in 2, so in 97% of them naming a chat message was the only
move available. `E_CIRCULAR_EVIDENCE` was a missing input, not a disobedient model.

The arm is OFF by default and these tests are mostly about why: the prompt is the cache key, and
the committed cache is how a judge reproduces every published number with no API key.
"""
from pathlib import Path

from ts.cache import request_hash
from ts.events import Event, EventIndex
from ts.ingest.replay import load_fixture
from ts.providers.base import build_chat_request
from ts.workflow.agent import (MAX_INLINE_CAPTIONS, MAX_INLINE_SEGMENTS, SYSTEM,
                               AudienceSignalAgent, stream_context)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals/fixtures"


def _index(*events):
    return EventIndex(events)


def speech(i, text, ts):
    return Event(f"tr_{i}", "transcript_segment", ts, {"text": text})


def frame(i, text, ts):
    return Event(f"frm_{i}", "frame_caption", ts, {"text": text})


# ------------------------------------------------------------- the default must not move

def test_the_default_opening_is_byte_identical_and_still_hits_the_cache():
    """The one test that protects the submission. `agent` is recorded; if this opening changes by
    a single character every committed entry becomes a miss and `make eval` stops reproducing
    without keys, which is the property the whole submission rests on."""
    start, end = 1788075308171, 1788075309123
    opening = (f"Analyse the window start_ms={start} end_ms={end}.\n"
               f"Call tools to see what happened, then answer.")
    request = build_chat_request(
        model="gpt-4.1-nano",
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": opening}],
        temperature=0.0, max_tokens=900, json_mode=True)

    digest = request_hash(request)

    assert (ROOT / f"cache/llm/{digest[:2]}/{digest}.json").is_file(), \
        "the agent's default opening no longer matches a recorded request"


def test_inlining_is_off_unless_asked_for():
    agent = AudienceSignalAgent(_index(), cache=None, provider=lambda req: {})

    assert agent.inline_context is False


def test_the_eval_does_not_run_the_new_arm_by_default():
    """`make eval` has to keep reproducing from the committed cache. An arm with no recording
    would raise CacheMiss and exit 3 on a clean clone."""
    source = (ROOT / "evals/run_eval.py").read_text(encoding="utf-8")

    assert "grounded: bool = False" in source
    assert 'ap.add_argument("--grounded"' in source
    assert "--grounded" not in (ROOT / "Makefile").read_text(encoding="utf-8")


# ----------------------------------------------------------------- what the model is shown

def test_the_window_speech_and_screen_arrive_with_their_ids():
    context = stream_context(
        _index(speech("a", "what the fuck is going on", 1_000),
               frame("b", "a word-guessing game is active", 2_000)), 0, 60_000)

    assert "id=tr_a" in context and "id=tr_b" not in context
    assert "id=frm_b" in context
    assert "SPEECH in this window" in context and "SCREEN in this window" in context


def test_a_window_with_neither_says_nothing_at_all():
    """A heading over an empty list tells the model there was context to find when there was not.
    On stableronaldo that is the truth for the whole capture: no speech, twelve minutes of it."""
    assert stream_context(_index(), 0, 60_000) == ""


def test_a_blank_transcript_segment_does_not_spend_a_slot():
    """Deepgram emits empty segments. An id over a blank line is one of twelve slots telling the
    model nothing."""
    context = stream_context(_index(speech("a", "   ", 1_000),
                                    speech("b", "real speech here", 2_000)), 0, 60_000)

    assert "id=tr_b" in context and "id=tr_a" not in context


def test_the_context_is_capped_so_the_call_does_not_grow():
    events = [speech(f"s{i}", f"segment {i}", 1_000 + i) for i in range(40)]
    events += [frame(f"f{i}", f"caption {i}", 2_000 + i) for i in range(40)]

    context = stream_context(_index(*events), 0, 60_000)

    assert context.count("id=tr_") == MAX_INLINE_SEGMENTS
    assert context.count("id=frm_") == MAX_INLINE_CAPTIONS


def test_long_text_is_clipped_rather_than_dropped():
    context = stream_context(_index(frame("a", "x" * 900, 1_000)), 0, 60_000)

    assert "…" in context
    assert len(context) < 500


def test_the_word_game_window_now_shows_the_model_the_answer():
    """The evidence for the whole item. stableronaldo w0's caption names the guessed word, and
    the agent emitted "No clear speech or on-screen content detected" over it."""
    index = load_fixture(FIXTURES / "stableronaldo_2026-08-30T0723")
    start = index.start_ms

    context = stream_context(index, start, start + 60_000)

    assert "ranger" in context
    assert "id=frm_" in context
    assert "SPEECH in this window" not in context, "this capture has no speech at all"


def test_the_grounded_opening_names_the_list_as_the_only_source_of_triggers():
    """Showing candidates without saying they are the candidates leaves the same ambiguity that
    produced the failure."""
    captured = {}

    def provider(request):
        captured["messages"] = request["messages"]
        return {"choices": [{"message": {"content": '{"action":"answer","cards":[]}'}}]}

    index = load_fixture(FIXTURES / "stableronaldo_2026-08-30T0723")

    class _PassThrough:
        hits = 0

        def call(self, request, fn):
            return fn(request)

    AudienceSignalAgent(index, _PassThrough(), provider=provider,
                        inline_context=True).run("t", index.start_ms, index.start_ms + 60_000)

    opening = captured["messages"][1]["content"]
    assert "id=frm_" in opening
    assert "must come from the list above" in opening
    assert '"unknown"' in opening, "abstention must stay available"
