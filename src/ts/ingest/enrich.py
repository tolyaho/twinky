"""Stage 2 of fixture creation: ENRICHMENT. **Requires API keys.**

Turns raw capture into the replayable fixture. Runs offline from the recorded bytes, so it can
happen hours after the stream ended.

    python -m ts.cli enrich --fixture evals/fixtures/<name>

    raw/audio.wav      -> transcript.jsonl   (Deepgram Nova-3, diarized, final segments only)
    raw/frames/*.jpg   -> frames.jsonl       (hosted VLM captions)
    raw/chat.jsonl     -> chat.jsonl         (copied; already pseudonymised at capture)

Every model response goes through `ts.cache`, so enrichment is itself recorded: re-running it in
replay mode reproduces identical output with no keys and no cost.

Rows are written WITHOUT an `id`. `ingest.replay` derives ids with `make_event_id` from
`(ts_ms, text)`, so the id rule lives in exactly one place and cannot drift between the writer
and the reader.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

from ..cache import ResponseCache
from ..providers import deepgram, vision

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[Path], Callable[[Dict[str, Any]], Dict[str, Any]]]


def load_meta(root: Path) -> Dict[str, Any]:
    return json.loads((root / "meta.json").read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    """Chunked on purpose - a fixture must never be held whole in memory."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dedupe(rows: Sequence[Dict[str, Any]], text_key: str = "text") -> List[Dict[str, Any]]:
    """Drop exact `(ts_ms, text)` repeats. Replay derives event ids from that pair and
    `EventIndex` rejects a fixture containing a duplicate id."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = (row["ts_ms"], row.get(text_key, ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _frames(frames_dir: Path) -> List[Tuple[int, Path]]:
    """Frames are named `<absolute_ts_ms>.jpg` by capture. The timestamp comes from the
    filename, never from file mtime or from the clock at enrichment time."""
    out: List[Tuple[int, Path]] = []
    for path in frames_dir.glob("*.jpg"):
        try:
            out.append((int(path.stem), path))
        except ValueError:
            raise ValueError(
                f"frame {path.name} is not named <absolute_ts_ms>.jpg; capture renames every "
                "frame to its absolute capture timestamp"
            ) from None
    return sorted(out)


def transcribe(root: Path, cache: ResponseCache, *,
               provider_factory: ProviderFactory = deepgram.DeepgramProvider
               ) -> List[Dict[str, Any]]:
    """raw/audio.wav -> transcript.jsonl rows. One row per final segment."""
    root = Path(root)
    meta = load_meta(root)
    audio = root / str(meta.get("audio") or "raw/audio.wav")
    if not audio.exists():
        raise FileNotFoundError(
            f"{audio} is missing; enrichment runs on a captured fixture "
            "(`python -m ts.cli capture --channel ...`)"
        )

    request = deepgram.build_stt_request(audio_sha256=_sha256_file(audio))
    response = cache.call(request, provider_factory(audio))
    rows = _dedupe(deepgram.segments_from_response(response, int(meta["start_ms"])))
    logger.info("transcribed %s: %d final segments", root.name, len(rows))
    return rows


def caption(root: Path, cache: ResponseCache, *,
            provider_factory: ProviderFactory = vision.VisionProvider
            ) -> List[Dict[str, Any]]:
    """raw/frames/*.jpg -> frames.jsonl rows. One cached call per frame, so a re-run after a
    partial failure only pays for the frames that are actually missing."""
    root = Path(root)
    frames_dir = root / "raw" / "frames"
    if not frames_dir.exists():
        raise FileNotFoundError(
            f"{frames_dir} is missing; enrichment runs on a captured fixture "
            "(`python -m ts.cli capture --channel ...`)"
        )

    frames = _frames(frames_dir)
    rows: List[Dict[str, Any]] = []
    for ts_ms, path in frames:
        request = vision.build_vision_request(image_sha256=_sha256_file(path))
        text = vision.caption_from_response(cache.call(request, provider_factory(path)))
        if text:
            rows.append({"ts_ms": ts_ms, "caption": text,
                         "frame": str(path.relative_to(root))})
    logger.info("captioned %s: %d/%d frames", root.name, len(rows), len(frames))
    return _dedupe(rows, text_key="caption")


def _write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(body, encoding="utf-8")


def enrich(root: Path, cache: ResponseCache, *,
           stt_factory: ProviderFactory = deepgram.DeepgramProvider,
           vision_factory: ProviderFactory = vision.VisionProvider) -> Path:
    root = Path(root)
    meta = load_meta(root)

    raw_chat = root / "raw" / "chat.jsonl"
    if raw_chat.exists():
        (root / "chat.jsonl").write_text(raw_chat.read_text(encoding="utf-8"), encoding="utf-8")

    # Written as each modality finishes, so a failure in the second one does not discard the
    # paid work already done by the first.
    segments = transcribe(root, cache, provider_factory=stt_factory)
    _write_jsonl(root / "transcript.jsonl", segments)

    captions = caption(root, cache, provider_factory=vision_factory)
    _write_jsonl(root / "frames.jsonl", captions)

    meta["enriched"] = True
    meta["enrichment"] = {
        "stt_model": deepgram.MODEL,
        "vision_model": vision.MODEL,
        "transcript_segments": len(segments),
        "frame_captions": len(captions),
        "cache": cache.stats(),
    }
    (root / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return root
