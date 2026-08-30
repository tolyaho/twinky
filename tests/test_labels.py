"""Group labels — the only model call in the reporting layer, and the only cosmetic one.

Two rules carry the whole design: a label is never evidence, and a label may never break the
page. Almost every test here is one of those two.
"""
from pathlib import Path

from ts.cache import CacheMiss, ResponseCache
from ts.ingest.replay import load_fixture
from ts.report.board import board, windows
from ts.report.labels import MAX_LABEL_CHARS, attach, label_groups

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals/fixtures"

GROUPS = [{"key": "t:violet", "count": 27, "samples": ["VIOLET MYERS", "is that violet"]},
          {"key": "p:wtf", "count": 10, "samples": ["WTF", "wtf..."]}]


class _Cache:
    """A cache whose behaviour each test chooses."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def call(self, request, provider):
        self.calls += 1
        return self.behaviour(request)


def _reply(content):
    return lambda request: {"choices": [{"message": {"content": content}}]}


# ------------------------------------------------------------ a label may never break the page

def test_a_cache_miss_in_replay_falls_back_to_the_token():
    """Replay raises on a miss on purpose — that is the keyless-reproduction mechanism. A demo
    that died because a cosmetic string was not recorded would trade the product for decoration.
    """
    def miss(request):
        raise CacheMiss("not recorded")

    assert label_groups(GROUPS, _Cache(miss)) == {}


def test_a_provider_failure_falls_back_to_the_token():
    def boom(request):
        raise RuntimeError("upstream is down")

    assert label_groups(GROUPS, _Cache(boom)) == {}


def test_a_malformed_reply_falls_back_to_the_token():
    for bad in ["not json at all", '{"labels": "a string"}', '{"labels": null}', "{}"]:
        assert label_groups(GROUPS, _Cache(_reply(bad))) == {}


def test_a_label_for_a_group_that_was_never_sent_is_dropped():
    """Attaching it would put a caption over messages the model never saw."""
    reply = _reply('{"labels": {"t:violet": "chat is naming someone", "t:ghost": "invented"}}')

    labels = label_groups(GROUPS, _Cache(reply))

    assert labels == {"t:violet": "chat is naming someone"}


def test_an_empty_label_is_not_attached():
    """The prompt asks for an empty string rather than an invented meaning, so honour it."""
    reply = _reply('{"labels": {"t:violet": "   ", "p:wtf": "a real line"}}')

    assert label_groups(GROUPS, _Cache(reply)) == {"p:wtf": "a real line"}


def test_a_long_label_is_clipped_rather_than_dropped():
    reply = _reply('{"labels": {"t:violet": "%s"}}' % ("x" * 400))

    assert len(label_groups(GROUPS, _Cache(reply))["t:violet"]) == MAX_LABEL_CHARS


def test_the_page_renders_when_nothing_was_labelled():
    """The real end-to-end version of the rule: a cold replay cache, and rows that still work."""
    index = load_fixture(FIXTURES / "marlon_2026-08-30T0715")
    start, end = windows(index)[6]
    result = board(index, start, end)

    attach(result["rows"], label_groups(result["rows"][0]["groups"], ResponseCache(mode="replay")))

    top = result["rows"][0]["groups"][0]
    assert top["label"] == "violet" and top["count"] == 27
    assert "meaning" not in top


# ------------------------------------------------------------------ a label is never evidence

def test_the_label_never_replaces_the_token_or_the_evidence():
    groups = [dict(GROUPS[0], label="violet", event_ids=["m1", "m2"])]
    rows = [{"groups": groups}]

    attach(rows, {"t:violet": "Chat is naming Violet Myers"})

    assert groups[0]["label"] == "violet", "the token the reducer produced must survive"
    assert groups[0]["count"] == 27
    assert groups[0]["event_ids"] == ["m1", "m2"]
    assert groups[0]["meaning"] == "Chat is naming Violet Myers"


def test_the_gate_never_reads_a_label():
    gate = (ROOT / "src/ts/provenance.py").read_text(encoding="utf-8")
    scorer = (ROOT / "evals/scorer.py").read_text(encoding="utf-8")

    for source in (gate, scorer):
        assert "meaning" not in source
        assert "label_groups" not in source


def test_the_ui_shows_the_token_beside_the_meaning():
    js = (ROOT / "src/ts/report/static/live.js").read_text(encoding="utf-8")
    block = js.split("function groupLine", 1)[1].split("\nfunction ", 1)[0]

    assert "gline-label" in block and "g.meaning" in block
    assert "g.samples" in block, "the messages under the caption are what it is judged against"


# ---------------------------------------------------------------------- cost and batching

def test_one_call_covers_a_whole_window():
    """Per-row batching cost 45 calls on an 11-window fixture. The groups come from the same
    minute of chat and the model reads them better together anyway."""
    cache = _Cache(_reply('{"labels": {}}'))

    label_groups(GROUPS * 8, cache)

    assert cache.calls == 1


def test_the_labelling_call_is_deterministic():
    captured = {}

    def capture(request):
        captured.update(request)
        return {"choices": [{"message": {"content": '{"labels": {}}'}}]}

    label_groups(GROUPS, _Cache(capture))

    assert captured["temperature"] == 0.0
    assert captured["model"] == "gpt-4.1-nano"


def test_the_recorded_labels_replay_with_no_key(monkeypatch):
    """34 calls were recorded once. Anyone can replay them for nothing."""
    for key in ("OPENAI_API_KEY", "TS_LLM_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TS_LLM_MODE", "replay")

    index = load_fixture(FIXTURES / "yugi_2026-08-30T0723")
    start, end = windows(index)[9]
    result = board(index, start, end)
    every = [g for r in result["rows"] for g in r["groups"]] + result["unattributed"]

    labels = label_groups(every, ResponseCache(mode="replay"),
                          trigger=next((r["trigger"]["text"] for r in result["rows"]), None))

    assert labels, "the recorded labels for this window are missing from the cache"
