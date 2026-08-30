"""The post-stream debrief.

It reorganises verified cards and adds no claim of its own, so the tests are about exactly that:
timecodes resolve to the triggering event, abstention stays visible, and nothing appears that a
card did not already say.
"""
import json
import shutil

import pytest

from ts import cli
from ts.ingest.replay import load_fixture
from ts.report.debrief import build, render_markdown, timecode

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"
START_MS = 1756399998000

META = {"fixture_id": "sample", "channel": "SYNTHETIC", "start_ms": START_MS,
        "duration_ms": 24000}

ANSWER_CARD = {
    "signal_id": "sig_00", "type": "audience_answer", "title": "Chat says лес",
    "distribution": {"лес": 9, "база": 6},
    "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
    "evidence": [f"msg_{i:04d}" for i in range(1, 13)],
    "confidence": 0.86, "window_ms": [START_MS, START_MS + 12000], "trace_id": "trc_a",
}
REACTION_CARD = {
    "signal_id": "sig_01", "type": "reaction", "title": "Chat laughs at the fall",
    "trigger": {"kind": "speech", "event_id": "tr_0002", "quote": "я упал"},
    "evidence": ["msg_0018", "msg_0019"], "confidence": 0.7,
    "window_ms": [START_MS + 12000, START_MS + 20000], "trace_id": "trc_b",
}
WARNING_CARD = {
    "signal_id": "sig_02", "type": "warning", "title": "Chat says the overlay covers the minimap",
    "trigger": {"kind": "unknown", "event_id": "unknown"},
    "evidence": ["msg_0027", "msg_0028", "msg_0029"], "confidence": 0.6,
    "window_ms": [START_MS + 20000, START_MS + 24000], "trace_id": "trc_c",
}
CARDS = [ANSWER_CARD, REACTION_CARD, WARNING_CARD]


@pytest.fixture
def index():
    return load_fixture(SAMPLE)


# --------------------------------------------------------------------------- timecodes
def test_timecode_is_an_offset_from_the_start_of_the_stream():
    assert timecode(START_MS, START_MS) == "00:00:00"
    assert timecode(START_MS + 3_723_000, START_MS) == "01:02:03"


def test_a_timecode_comes_from_the_triggering_event_not_the_window(index):
    doc = build(CARDS, META, index)

    answer = doc["sections"]["audience_answers"][0]
    assert answer["ts_source"] == "trigger"
    assert answer["ts_ms"] == index.get("tr_0001").ts_ms
    assert answer["at"] == "00:00:02"


def test_a_card_with_no_resolvable_trigger_falls_back_to_the_window_and_says_so(index):
    doc = build(CARDS, META, index)

    warning = doc["sections"]["warnings"][0]
    assert warning["ts_source"] == "window"
    assert "window start, not the exact moment" in render_markdown(doc)


# --------------------------------------------------------------------------- sections
def test_cards_are_filed_by_type(index):
    sections = build(CARDS, META, index)["sections"]

    assert [e["signal_id"] for e in sections["audience_answers"]] == ["sig_00"]
    assert [e["signal_id"] for e in sections["reaction_waves"]] == ["sig_01"]
    assert [e["signal_id"] for e in sections["warnings"]] == ["sig_02"]
    assert sections["unanswered_questions"] == []


def test_clip_candidates_are_ranked_by_evidence_and_exclude_unprovable_causes(index):
    clips = build(CARDS, META, index)["sections"]["clip_candidates"]

    assert [e["signal_id"] for e in clips] == ["sig_00", "sig_01"]
    # a card whose cause is unknown has no moment to clip
    assert "sig_02" not in [e["signal_id"] for e in clips]


def test_themes_ignore_words_the_model_wrote_in_the_title(index):
    """Counting title words measured the summariser's phrasing, not the session: the first
    version of this section returned "chat", "says" and "the"."""
    doc = build(CARDS, META, index)

    terms = {t["term"] for t in doc["sections"]["recurring_themes"]}
    assert not terms & {"chat", "says", "the"}
    # three unrelated signals in half a minute genuinely share no theme
    assert doc["sections"]["recurring_themes"] == []


def test_a_term_carried_by_two_signals_becomes_a_theme(index):
    second_poll = dict(ANSWER_CARD, signal_id="sig_03",
                       distribution={"лес": 4, "болото": 2},
                       trigger={"kind": "speech", "event_id": "tr_0001", "quote": "в лес?"})

    doc = build([ANSWER_CARD, second_poll], META, index)

    terms = {t["term"]: t["cards"] for t in doc["sections"]["recurring_themes"]}
    assert terms["лес"] == 2
    assert "болото" not in terms  # carried by one card only


def test_stopwords_do_not_become_themes(index):
    noisy = [dict(ANSWER_CARD, signal_id=f"sig_1{i}", distribution=None,
                  trigger={"kind": "speech", "event_id": "tr_0001", "quote": "или что это"})
             for i in range(2)]

    assert build(noisy, META, index)["sections"]["recurring_themes"] == []


# --------------------------------------------------------------------------- rendering
def test_an_unprovable_warning_is_rendered_as_an_abstention(index):
    md = render_markdown(build(CARDS, META, index))

    assert "Cause: **not established.**" in md
    assert "не установлена" not in md  # the document is English; no accidental mixing


def test_every_section_heading_is_present_even_when_empty(index):
    md = render_markdown(build(CARDS, META, index))

    for title in ("Audience answers", "Questions chat asked that were never answered",
                  "Reaction waves", "Warnings", "Clip candidates", "Recurring themes"):
        assert f"## {title}" in md
    assert "_Nothing in this run._" in md  # unanswered questions section


def test_no_verified_cards_is_reported_as_a_result_not_an_error():
    md = render_markdown(build([], META, None))

    assert "## No verified signals" in md
    assert "That is a result, not an error" in md


def test_distribution_is_rendered_with_shares(index):
    md = render_markdown(build([ANSWER_CARD], META, index))

    assert "**лес** 9 (60%)" in md and "**база** 6 (40%)" in md


# --------------------------------------------------------------------------- CLI wiring
def test_debrief_before_a_replay_says_which_command_to_run(tmp_path, monkeypatch, capsys):
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["debrief", "--fixture", "fixture", "--out", "out"])

    assert rc == 4
    assert "make replay" in capsys.readouterr().err


def test_debrief_writes_markdown_and_json_from_replay_output(tmp_path, monkeypatch):
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "sample.agent.json").write_text(json.dumps({
        "windows": [{"verified": CARDS, "rejected": []}]}), encoding="utf-8")

    assert cli.main(["debrief", "--fixture", "fixture", "--out", "out"]) == 0

    doc = json.loads((tmp_path / "out" / "sample.debrief.json").read_text(encoding="utf-8"))
    assert doc["verified_cards"] == 3
    assert "# Post-stream debrief — sample" in \
           (tmp_path / "out" / "sample.debrief.md").read_text(encoding="utf-8")


def test_debrief_reads_only_verified_cards(tmp_path, monkeypatch):
    """A card the gate rejected must never reach the document a streamer reads."""
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "sample.agent.json").write_text(json.dumps({
        "windows": [{"verified": [ANSWER_CARD],
                     "rejected": [dict(REACTION_CARD, signal_id="sig_bad")]}]}), encoding="utf-8")

    cli.main(["debrief", "--fixture", "fixture", "--out", "out"])

    md = (tmp_path / "out" / "sample.debrief.md").read_text(encoding="utf-8")
    assert "sig_bad" not in md
