"""One isolated live job. Stdout is bounded NDJSON; no secrets or hidden reasoning in events."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import sys
from .cache import ResponseCache
from .events import EventIndex
from .ingest.replay import load_fixture
from .live_limits import LIMITS, LimitedCache, QuotaExceeded
from .provenance import CURRENT_GATE
from .workflow.agent import AudienceSignalAgent


def process(index, cache, emit, *, case_id, start_ms=None, end_ms=None):
    """Shared real agent/gate seam, also used by the offline API integration test."""
    start_ms = index.start_ms if start_ms is None else start_ms
    end_ms = index.end_ms + 1 if end_ms is None else end_ms
    context = [{"event_id": e.event_id, "type": e.type, "ts_ms": e.ts_ms, "text": e.text[:500]}
               for e in index if e.type != "chat_message"][:128]
    for offset in range(0, len(context), 12):
        emit("context", {"events": context[offset:offset+12],
                         "chat_messages": sum(e.type == "chat_message" for e in index)})
    result = AudienceSignalAgent(index, cache, observer=emit).run(case_id, start_ms, end_ms)
    # File paths are private worker details. All evidence uses the existing event IDs.
    cards = result["verified"] + result["rejected"]
    cited = set(mid for c in cards for mid in c.get("evidence", []))
    evidence = [{"event_id": e.event_id, "ts_ms": e.ts_ms, "text": e.text[:500]}
                for e in index if e.event_id in cited][:30]
    for offset in range(0, len(evidence), 12):
        emit("context", {"evidence": evidence[offset:offset+12]})
    return {"cards": cards, "gate_version": CURRENT_GATE,
            "causal_claim": "hypothesis", "steps": result["steps"], "cache": cache.stats()}


def run_live(channel, work, emit):
    from .ingest.capture import capture
    from .ingest.enrich import enrich
    os.environ["TS_LLM_MODE"] = "record"
    os.environ["TS_TRACE_DIR"] = str(work / "traces")
    emit("progress", {"phase": "capture", "capture_seconds": LIMITS.capture_seconds})
    root = asyncio.run(capture(channel, 1, work / "capture", bounded=True))
    audio = root / "raw/audio.wav"
    frames = list((root / "raw/frames").glob("*.jpg"))
    if (audio.stat().st_size > LIMITS.max_audio_bytes or len(frames) > LIMITS.max_frames or
        any(p.stat().st_size > LIMITS.max_frame_bytes for p in frames)):
        raise QuotaExceeded("media_volume_exceeded")
    cache = LimitedCache(work / "cache", mode="record")
    emit("progress", {"phase": "enrichment", "frames": len(frames)})
    enrich(root, cache)
    index = load_fixture(root)
    if not any(e.type == "chat_message" for e in index):
        raise RuntimeError("empty_chat_capture")
    # Restrict tool-visible context to this capture; no adjacent session or future events.
    index = EventIndex(index.window(index.start_ms, index.start_ms + 60_000))
    result = process(index, cache, emit, case_id="live_session")
    result["usage"] = {"calls": cache.calls, "requested_completion_tokens": cache.tokens,
                       "text_input_bytes": cache.input_bytes}
    return result


def main():
    # The parent uses a private cwd and supplies only a normalized channel, never credentials.
    work = Path.cwd()
    def emit(kind, data):
        body = json.dumps({"type": kind, "data": data}, ensure_ascii=False)
        if len(body.encode()) > LIMITS.max_event_bytes:
            raise QuotaExceeded("event_size_exceeded")
        print(body, flush=True)
    try:
        from .twitch import TwitchStatus, TwitchUnavailable
        try:
            status = TwitchStatus().lookup(sys.argv[1])
        except TwitchUnavailable:
            emit("worker_terminal", {"state": "unavailable"})
            return 0
        emit("context", {"channel_status": status})
        if not status["live"]:
            emit("worker_terminal", status)
            return 0
        emit("status", {"state": "running"})
        result = run_live(sys.argv[1], work, emit)
        emit("worker_result", result)
        return 0
    except QuotaExceeded:
        emit("error", {"code": "resource_limit", "message": "Worker quota exceeded"})
    except Exception:
        emit("error", {"code": "pipeline_failed", "message": "Capture, enrichment or analysis failed"})
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
