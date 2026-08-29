"""Enrichment on FAKE providers. No network, no keys, no cost.

The point of these tests is the property the whole submission rests on: enrichment is recorded
once and replays byte-identically with the provider unplugged.
"""
import json
from pathlib import Path

import pytest

from ts.cache import CacheMiss, ResponseCache
from ts.ingest.enrich import caption, enrich, transcribe
from ts.ingest.replay import load_fixture
from ts.providers import deepgram, vision

START_MS = 1724951200000

DEEPGRAM_UTTERANCES = {
    "results": {
        "utterances": [
            {"start": 1.5, "end": 3.25, "speaker": 0,
             "transcript": "куда идти  -  в лес или на базу?"},
            {"start": 4.0, "end": 5.0, "speaker": 1, "transcript": "иди налево"},
            {"start": 6.0, "end": 6.5, "speaker": 0, "transcript": "   "},
        ]
    }
}

DEEPGRAM_WORDS_ONLY = {
    "results": {
        "channels": [{"alternatives": [{"words": [
            {"punctuated_word": "Куда", "start": 1.0, "end": 1.3, "speaker": 0},
            {"punctuated_word": "идти?", "start": 1.3, "end": 1.8, "speaker": 0},
            # same speaker, but a 3 s pause -> new segment
            {"punctuated_word": "Ладно.", "start": 4.8, "end": 5.2, "speaker": 0},
            # speaker change -> new segment even with no pause
            {"word": "налево", "start": 5.2, "end": 5.6, "speaker": 1},
        ]}]}]
    }
}


def _vision_response(text):
    return {"choices": [{"message": {"content": text}}]}


def make_fixture(tmp_path, *, frames=(START_MS + 2000, START_MS + 32000)):
    root = tmp_path / "fake_2026-08-29T2140"
    (root / "raw" / "frames").mkdir(parents=True)
    (root / "raw" / "audio.wav").write_bytes(b"RIFF....fake wav bytes")
    (root / "raw" / "chat.jsonl").write_text(
        json.dumps({"id": "msg_1", "ts_ms": START_MS + 2500, "author": "u1",
                    "text": "налево"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    for i, ts in enumerate(frames):
        (root / "raw" / "frames" / f"{ts}.jpg").write_bytes(b"\xff\xd8fake-jpeg-%d" % i)
    (root / "meta.json").write_text(json.dumps({
        "fixture_id": root.name, "channel": "fake", "start_ms": START_MS,
        "audio": "raw/audio.wav", "frames": len(frames), "enriched": False,
    }), encoding="utf-8")
    return root


class FakeProvider:
    """One instance per media file, matching the real providers' shape."""

    def __init__(self, response, calls):
        self.response = response
        self.calls = calls

    def factory(self, path):
        def call(request):
            self.calls.append((Path(path).name, request))
            return self.response
        return call


class ExplodingProvider:
    def __call__(self, request):  # pragma: no cover - the test fails if this ever runs
        raise AssertionError("provider called in replay mode")


def _factories(calls, *, caption_text="A forest path. HUD shows 42 HP. Chat overlay: text unclear"):
    stt = FakeProvider(DEEPGRAM_UTTERANCES, calls).factory
    vis = FakeProvider(_vision_response(caption_text), calls).factory
    return stt, vis


# --------------------------------------------------------------------------- STT parsing
def test_utterances_become_absolute_final_segments():
    rows = deepgram.segments_from_response(DEEPGRAM_UTTERANCES, START_MS)

    assert [r["ts_ms"] for r in rows] == [START_MS + 1500, START_MS + 4000]
    assert rows[0]["end_ms"] == START_MS + 3250
    assert rows[0]["text"] == "куда идти - в лес или на базу?"  # whitespace normalised
    assert rows[0]["speaker"] == "spk_0" and rows[1]["speaker"] == "spk_1"
    assert all(r["final"] for r in rows)  # interim segments never enter a fixture


def test_words_fallback_splits_on_speaker_change_and_pause():
    rows = deepgram.segments_from_response(DEEPGRAM_WORDS_ONLY, START_MS)

    assert [r["text"] for r in rows] == ["Куда идти?", "Ладно.", "налево"]
    assert [r["speaker"] for r in rows] == ["spk_0", "spk_0", "spk_1"]
    assert rows[0]["ts_ms"] == START_MS + 1000


def test_empty_response_yields_no_segments():
    assert deepgram.segments_from_response({}, START_MS) == []


# --------------------------------------------------------------------------- vision parsing
def test_caption_is_normalised_and_capped():
    assert vision.caption_from_response(_vision_response("  a\n b  ")) == "a b"
    long = vision.caption_from_response(_vision_response("x" * 900))
    assert len(long) == vision.MAX_CAPTION_CHARS


def test_media_bytes_never_enter_the_cache_key(tmp_path):
    root = make_fixture(tmp_path)
    calls = []
    stt, vis = _factories(calls)
    cache = ResponseCache(tmp_path / "cache", mode="record")

    enrich(root, cache, stt_factory=stt, vision_factory=vis)

    for _, request in calls:
        blob = json.dumps(request)
        assert "base64" not in blob and "data:image" not in blob
        assert len(blob) < 2000
    assert len(calls[0][1]["audio_sha256"]) == 64


# --------------------------------------------------------------------------- fixture wiring
def test_frame_timestamp_comes_from_the_filename(tmp_path):
    root = make_fixture(tmp_path, frames=(START_MS + 7000,))
    calls = []
    _, vis = _factories(calls)

    rows = caption(root, ResponseCache(tmp_path / "cache", mode="record"),
                   provider_factory=vis)

    assert rows[0]["ts_ms"] == START_MS + 7000
    assert rows[0]["frame"] == str(Path("raw/frames") / f"{START_MS + 7000}.jpg")


def test_badly_named_frame_is_rejected(tmp_path):
    root = make_fixture(tmp_path)
    (root / "raw" / "frames" / "frame-001.jpg").write_bytes(b"\xff\xd8")
    calls = []
    _, vis = _factories(calls)

    with pytest.raises(ValueError, match="absolute_ts_ms"):
        caption(root, ResponseCache(tmp_path / "cache", mode="record"), provider_factory=vis)


def test_missing_audio_is_a_loud_error(tmp_path):
    root = make_fixture(tmp_path)
    (root / "raw" / "audio.wav").unlink()

    with pytest.raises(FileNotFoundError, match="capture"):
        transcribe(root, ResponseCache(tmp_path / "cache", mode="record"))


def test_enrich_writes_the_replayable_fixture(tmp_path):
    root = make_fixture(tmp_path)
    calls = []
    stt, vis = _factories(calls)

    enrich(root, ResponseCache(tmp_path / "cache", mode="record"),
           stt_factory=stt, vision_factory=vis)

    meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
    assert meta["enriched"] is True
    assert meta["enrichment"]["transcript_segments"] == 2
    assert meta["enrichment"]["frame_captions"] == 2
    assert meta["enrichment"]["stt_model"] == deepgram.MODEL

    # one STT call for the whole wav, one vision call per frame
    assert len(calls) == 3
    assert (root / "chat.jsonl").exists()

    index = load_fixture(root)
    kinds = sorted({e.type for e in index})
    assert kinds == ["chat_message", "frame_caption", "transcript_segment"]
    # ids are derived by the loader, so the writer and the reader cannot drift apart
    assert all(e.event_id for e in index)


def test_second_run_replays_from_cache_with_the_provider_unplugged(tmp_path):
    root = make_fixture(tmp_path)
    cache_dir = tmp_path / "cache"
    calls = []
    stt, vis = _factories(calls)

    enrich(root, ResponseCache(cache_dir, mode="record"), stt_factory=stt, vision_factory=vis)
    first = {name: (root / name).read_text(encoding="utf-8")
             for name in ("transcript.jsonl", "frames.jsonl")}

    exploding = lambda path: ExplodingProvider()  # noqa: E731
    replay_cache = ResponseCache(cache_dir, mode="replay")
    enrich(root, replay_cache, stt_factory=exploding, vision_factory=exploding)

    assert {name: (root / name).read_text(encoding="utf-8")
            for name in first} == first
    assert replay_cache.stats() == {"hits": 3, "misses": 0}


def test_replay_without_a_recording_is_a_hard_error(tmp_path):
    root = make_fixture(tmp_path)
    exploding = lambda path: ExplodingProvider()  # noqa: E731

    with pytest.raises(CacheMiss):
        enrich(root, ResponseCache(tmp_path / "cache", mode="replay"),
               stt_factory=exploding, vision_factory=exploding)
