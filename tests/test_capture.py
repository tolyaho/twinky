from ts.ingest.capture import parse_privmsg, pseudonym

LINE = ("@badge-info=;display-name=SomeUser;id=abc-123;room-id=999;"
        "tmi-sent-ts=1756400000000;user-type= "
        ":someuser!someuser@someuser.tmi.twitch.tv PRIVMSG #chan :лес или база?")


def test_parses_tagged_privmsg():
    r = parse_privmsg(LINE)
    assert r["id"] == "abc-123"
    assert r["ts_ms"] == 1756400000000       # Twitch's timestamp, not local arrival time
    assert r["text"] == "лес или база?"
    assert r["login"] == "someuser"


def test_text_containing_colons_survives():
    line = LINE.replace(":лес или база?", ":go here: https://x.com/a")
    assert parse_privmsg(line)["text"] == "go here: https://x.com/a"


def test_non_privmsg_ignored():
    assert parse_privmsg("PING :tmi.twitch.tv") is None
    assert parse_privmsg(":tmi.twitch.tv 001 justinfan1 :Welcome") is None


def test_untagged_privmsg_ignored():
    assert parse_privmsg(":u!u@u.tmi.twitch.tv PRIVMSG #c :hi") is None


def test_pseudonym_is_stable_case_insensitive_and_salted():
    assert pseudonym("SomeUser", "s") == pseudonym("someuser", "s")
    assert pseudonym("someuser", "s") != pseudonym("someuser", "other-salt")
    assert "someuser" not in pseudonym("someuser", "s")


# --------------------------------------------------------------------------- media capture
# The recorder has never run against a live stream (RISKS #21) and it is the one time-critical
# step of the project. Everything below the network boundary is exercised here so that when it
# does run, a failure means Twitch or ffmpeg — not this code.
import json
import subprocess as _subprocess

import pytest

from ts.ingest import capture as cap
from ts.ingest.enrich import enrich
from ts.ingest.replay import load_fixture

START_MS = 1756400000000


def _frames(root, count, name=lambda i: f"{i + 1:06d}.jpg"):
    d = root / "raw" / "frames"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (d / name(i)).write_bytes(b"\xff\xd8jpg")
    return d


def test_frames_are_stamped_with_absolute_timestamps(tmp_path):
    frames = _frames(tmp_path, 3)

    assert cap.stamp_frames(frames, START_MS, interval=30) == 3
    assert sorted(p.name for p in frames.glob("*.jpg")) == [
        f"{START_MS}.jpg", f"{START_MS + 30000}.jpg", f"{START_MS + 60000}.jpg"]


def test_stamping_twice_leaves_already_stamped_frames_alone(tmp_path):
    """Capture is the step that gets retried. A second pass must not renumber real timestamps
    from zero against a new start time."""
    frames = _frames(tmp_path, 2)
    cap.stamp_frames(frames, START_MS, interval=30)
    before = sorted(p.name for p in frames.glob("*.jpg"))

    assert cap.stamp_frames(frames, START_MS + 999_000, interval=30) == 0
    assert sorted(p.name for p in frames.glob("*.jpg")) == before


def test_capture_refuses_to_write_into_a_used_directory(tmp_path, monkeypatch):
    _frames(tmp_path, 1)
    monkeypatch.setattr(cap, "_open_stream", lambda *a, **kw: pytest.fail("must not open a stream"))

    with pytest.raises(RuntimeError, match="already holds 1 frames"):
        cap.capture_media("somechannel", tmp_path, seconds=1)


class _FakeStream:
    def open(self):
        class _FD:
            def read(self, _n): return b""
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _FD()


class _FakeFfmpeg:
    """Stands in for the ffmpeg subprocess, and writes what ffmpeg would have written."""

    def __init__(self, root, frames=2, audio_bytes=4096, returncode=0):
        self.root, self.frames, self.audio_bytes, self.returncode = \
            root, frames, audio_bytes, returncode
        self.stdin = type("W", (), {"write": lambda s, b: None, "close": lambda s: None})()
        self.stderr = type("E", (), {"read": lambda s: b"ffmpeg said no"})()

    def wait(self, timeout=None):
        _frames(self.root, self.frames)
        audio = self.root / "raw" / "audio.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"\0" * self.audio_bytes)
        return self.returncode


def _fake_media(monkeypatch, tmp_path, **kw):
    monkeypatch.setattr(cap, "_open_stream", lambda *a, **k: (_FakeStream(), "480p"))
    proc = _FakeFfmpeg(tmp_path, **kw)
    monkeypatch.setattr(_subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(cap.subprocess, "Popen", lambda *a, **k: proc)
    return proc


def test_a_successful_capture_reports_what_replay_needs(tmp_path, monkeypatch):
    _fake_media(monkeypatch, tmp_path, frames=3)

    meta = cap.capture_media("somechannel", tmp_path, seconds=1, interval=30)

    assert meta["frames"] == 3 and meta["quality"] == "480p"
    assert meta["audio"] == "raw/audio.wav"          # relative to the fixture root
    assert meta["frame_interval_s"] == 30
    assert isinstance(meta["start_ms"], int)


def test_a_capture_that_produced_nothing_fails_instead_of_claiming_success(tmp_path, monkeypatch):
    """Otherwise meta.json declares a good fixture and the emptiness surfaces hours later, at
    enrichment time, with the broadcast over."""
    _fake_media(monkeypatch, tmp_path, frames=0)

    with pytest.raises(RuntimeError, match="produced 0 frames"):
        cap.capture_media("somechannel", tmp_path, seconds=1)


def test_silent_audio_failure_is_caught(tmp_path, monkeypatch):
    _fake_media(monkeypatch, tmp_path, frames=2, audio_bytes=44)   # a bare WAV header

    with pytest.raises(RuntimeError, match="44 bytes of audio"):
        cap.capture_media("somechannel", tmp_path, seconds=1)


def test_an_ffmpeg_failure_surfaces_its_own_stderr(tmp_path, monkeypatch):
    _fake_media(monkeypatch, tmp_path, returncode=1)

    with pytest.raises(RuntimeError, match="ffmpeg exited 1"):
        cap.capture_media("somechannel", tmp_path, seconds=1)


# --------------------------------------------------------------------------- the seam
def test_a_captured_fixture_enriches_and_loads_without_a_hand_edit(tmp_path, monkeypatch):
    """capture -> enrich -> load_fixture across the real seam. This is the join that decides
    whether a recorded fixture is usable, and it is discovered at 5am if it is wrong."""
    from ts.cache import ResponseCache

    root = tmp_path / "somechannel_2026-08-30T0500"
    _fake_media(monkeypatch, root, frames=2)
    media = cap.capture_media("somechannel", root, seconds=1, interval=30)
    (root / "raw" / "chat.jsonl").write_text(
        json.dumps({"id": "msg_1", "ts_ms": media["start_ms"] + 500,
                    "author": "u_abc", "text": "лес"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (root / "meta.json").write_text(json.dumps(
        {"fixture_id": root.name, "channel": "somechannel", "enriched": False, **media}),
        encoding="utf-8")

    stt = lambda path: (lambda req: {"results": {"utterances": [
        {"start": 0.5, "end": 2.0, "speaker": 0, "transcript": "куда идти"}]}})
    vis = lambda path: (lambda req: {"choices": [{"message": {"content": "A forest path."}}]})
    enrich(root, ResponseCache(tmp_path / "cache", mode="record"),
           stt_factory=stt, vision_factory=vis)

    index = load_fixture(root)
    assert sorted({e.type for e in index}) == \
           ["chat_message", "frame_caption", "transcript_segment"]
    frame_times = sorted(e.ts_ms for e in index if e.type == "frame_caption")
    assert frame_times == [media["start_ms"], media["start_ms"] + 30000]
