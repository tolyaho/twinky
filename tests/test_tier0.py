"""Tier 0 live chat: a real broadcast, no key, no model, no cost.

The point of the tier is what it CANNOT do. There is no audio and no screen, so no group has a
cause and every row is unattributed — the same argument the chat-only ablation makes in the
evaluation, running live. These tests are mostly about keeping that honest and keeping the free
path free.
"""
from pathlib import Path

from ts.events import Event
from ts.live_chat import (MAX_LIVE_GROUPS, TIER0_MAX_SECONDS, TRAILING_MS, _live_salt,
                          _snapshot, session)

ROOT = Path(__file__).resolve().parents[1]


def code(path):
    """Source with docstrings and comments removed.

    House rule, learned five times now: a guard that greps raw source fires on the comment
    explaining why the thing it forbids is not there. Assert against code, explain in prose.
    """
    import io
    import tokenize

    src = (ROOT / path).read_text(encoding="utf-8")
    out, prev_end, prev_type = [], (1, 0), tokenize.INDENT
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and prev_type in (
                tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL):
            continue                       # a bare string statement is a docstring
        out.append(tok.string)
        prev_type = tok.type if tok.type != tokenize.NL else prev_type
    return " ".join(out)


def chat(i, text, ts, author=None):
    return Event(f"m{i}", "chat_message", ts, {"text": text, "author": author or f"u{i}"})


def test_the_snapshot_groups_with_the_same_rules_replay_uses():
    events = [chat(i, t, 1_000 + i) for i, t in
              enumerate(["violet", "VIOLET", "Violet", "violet.", "unrelated thing"])]

    snap = _snapshot(events, 1_010)

    assert [(g["label"], g["count"]) for g in snap["groups"]] == [("viol…", 4)]
    assert snap["summary"] == {"messages": 5, "groups": 1, "grouped": 4, "ungrouped": 1}


def test_this_tier_has_no_cause_to_give():
    """No transcript and no captions, so the rail reports a silent window and no frame ever
    arrives. A board that implied otherwise would be claiming an input it does not have."""
    snap = _snapshot([chat(i, "violet", 1_000 + i) for i in range(4)], 1_010)

    assert snap["rail"]["silent"] is True
    assert snap["rail"]["frame_captions"] == []
    assert snap["rail"]["speech_segments"] == 0


def test_the_trailing_window_matches_replay():
    """Live and replay have to mean the same thing by 'this minute', or the two boards are not
    comparable and the live demo proves nothing about the recorded one."""
    from ts.report.board import TICK_SPAN_MS

    assert TRAILING_MS == TICK_SPAN_MS == 60_000


def test_messages_older_than_the_trailing_window_drop_out():
    events = [chat(1, "violet", 1_000), *[chat(i, "violet", 100_000 + i) for i in range(2, 6)]]

    snap = _snapshot(events, 100_010)

    assert snap["summary"]["messages"] == 4, "a message from two minutes ago is not this minute"


def test_the_live_salt_is_per_session_and_never_written_down():
    """`ingest.capture._salt()` reads or creates `.capture_salt` so a RECORDED fixture keeps
    stable pseudonyms. Nothing here is recorded, and a live path that writes a file the
    guardrails forbid committing is a trap."""
    assert _live_salt() != _live_salt()

    body = code("src/ts/live_chat.py")
    assert "capture_salt" not in body, "no salt file is touched"
    assert "_salt (" not in body.replace("_live_salt (", "")


def test_a_live_viewer_is_pseudonymised_even_though_nothing_is_stored():
    """A demo gets filmed. A real viewer's login does not belong in a submission video."""
    body = code("src/ts/live_chat.py")

    assert 'pseudonym ( row [ "login" ] , salt )' in body
    assert body.count('"login"') == 1, "a raw login must not reach the browser"


def test_tier_zero_writes_nothing_at_all():
    """No fixture, no cache entry, no trajectory: a live session cannot contaminate anything a
    judge reproduces."""
    body = code("src/ts/live_chat.py")

    for forbidden in ["open (", "write_text", "mkdir", "ResponseCache", "Trace ("]:
        assert forbidden not in body, f"Tier 0 touches the filesystem via {forbidden}"


def test_the_status_line_states_what_this_tier_cannot_do():
    source = (ROOT / "src/ts/live_chat.py").read_text(encoding="utf-8")

    assert "no cost" in source and "every group is unattributed" in source


def test_a_missing_dependency_stops_cleanly_rather_than_crashing(monkeypatch):
    """A judge on the base install has websockets; one who edited it might not. The message has
    to name the fix and say replay is unaffected."""
    import builtins

    real = builtins.__import__

    def no_websockets(name, *args, **kwargs):
        if name == "websockets":
            raise ImportError("no websockets")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_websockets)
    events = list(session("somechannel"))

    assert len(events) == 1
    assert events[0]["reason"] == "dependency"
    assert "Replay is unaffected" in events[0]["message"]


def test_the_session_is_time_boxed():
    assert TIER0_MAX_SECONDS == 600
    assert MAX_LIVE_GROUPS <= 8


def test_the_route_sanitises_the_channel_name():
    """A channel comes from a text field. It reaches a URL and a JOIN, so it is stripped to what
    a Twitch login can actually be."""
    source = (ROOT / "src/ts/report/serve.py").read_text(encoding="utf-8")
    handler = source.split("def _live_chat", 1)[1].split("\n    def ", 1)[0]

    assert 're.sub(r"[^a-zA-Z0-9_]", "", params.get("channel", ""))[:25].lower()' in handler


def test_the_free_tier_is_a_separate_route_from_the_paid_one():
    """`/api/live` spends money per window. A viewer must not reach it by accident."""
    source = (ROOT / "src/ts/report/serve.py").read_text(encoding="utf-8")

    assert "/api/live_chat" in source
    handler = source.split("def _live_chat", 1)[1].split("\n    def ", 1)[0]
    assert "enrich" not in handler and "AudienceSignalAgent" not in handler


def test_the_badge_is_written_from_the_server_not_from_the_tab():
    """The control carries intent; the badge carries what the server reports. They are two
    different things so that a tab which thinks it is live over a replaying server cannot say so.
    """
    js = (ROOT / "src/ts/report/static/live.js").read_text(encoding="utf-8")
    html = (ROOT / "src/ts/report/static/index.html").read_text(encoding="utf-8")

    assert "`${s.mode.toUpperCase()} · TIER ${s.tier} · $0.00`" in js
    assert 'id="mode-replay"' in html and 'id="mode-live"' in html


def test_the_paid_escalation_says_it_is_paid_before_it_is_clicked():
    html = (ROOT / "src/ts/report/static/index.html").read_text(encoding="utf-8")

    assert "costs money" in html


def test_a_silent_channel_says_so_rather_than_looking_broken():
    """Anonymous IRC joins an offline channel happily and then delivers nothing, so "connected"
    followed by an empty feed is indistinguishable from a fault — which is how it reads on
    camera. Found while walking the shot list: `#jynxzi` returned 0 messages in 9 seconds."""
    source = code("src/ts/live_chat.py")

    assert "QUIET_AFTER_S" in source
    assert '"quiet"' in source
    text = (ROOT / "src/ts/live_chat.py").read_text(encoding="utf-8")
    assert "probably offline" in text


def test_a_status_without_a_mode_does_not_kill_the_handler(js_source):
    """The quiet status carries no `mode`, and the badge was written from `s.mode.toUpperCase()`
    unconditionally — an absent mode would throw and take the whole live session with it."""
    js = js_source("live.js")
    block = js.split("function watchLiveChat", 1)[1].split("\nfunction ", 1)[0]

    assert "if (s.mode) {" in block
    assert block.index("if (s.mode) {") < block.index("s.mode.toUpperCase()")
