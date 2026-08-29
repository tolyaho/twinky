"""Speech-to-text adapter: Deepgram Nova-3, prerecorded REST endpoint.

`record` mode only. Replay never reaches a provider: the transcript is already in the fixture
and every Deepgram response is in `cache/llm/`.

The cache key names the audio by SHA-256 instead of carrying the bytes. The cache is committed
so judges can reproduce with no keys, and a ten-minute 16 kHz WAV is ~19 MB - it does not belong
in a cache entry.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

MODEL = "nova-3-general"
URL = "https://api.deepgram.com/v1/listen"

# Only used by the words fallback: the same speaker pausing longer than this starts a new
# segment. When Deepgram returns utterances they are already final segments.
SEGMENT_GAP_MS = 1500


def build_stt_request(*, audio_sha256: str, model: str = MODEL, language: str = "multi",
                      diarize: bool = True, smart_format: bool = True,
                      utterances: bool = True) -> Dict[str, Any]:
    """Canonical request. This dict IS the cache key - keep it free of anything that varies
    between machines or runs."""
    return {
        "provider": "deepgram",
        "model": model,
        "language": language,
        "diarize": diarize,
        "smart_format": smart_format,
        "utterances": utterances,
        "audio_sha256": audio_sha256,
    }


def query_params(request: Dict[str, Any]) -> Dict[str, str]:
    """Cache-key request -> Deepgram query string. `audio_sha256` is ours, not theirs."""
    params = {k: str(request[k]) for k in ("model", "language")}
    params.update({k: "true" if request[k] else "false"
                   for k in ("diarize", "smart_format", "utterances")})
    return params


class DeepgramProvider:
    """Bound to one audio file, so it fits the one-argument provider shape `ResponseCache.call`
    expects. Reads the file lazily: a cache hit never touches the media."""

    def __init__(self, audio_path: Path | str, api_key: Optional[str] = None,
                 url: str = URL) -> None:
        self.audio_path = Path(audio_path)
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.url = url

    def __call__(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY is unset. Enrichment is a record-mode step run once per "
                "fixture; the graded path replays the fixture and needs no key."
            )
        import httpx  # imported lazily so replay-mode runs need no network stack
        r = httpx.post(
            self.url,
            params=query_params(request),
            headers={"Authorization": f"Token {self.api_key}", "Content-Type": "audio/wav"},
            content=self.audio_path.read_bytes(),
            timeout=600.0,
        )
        r.raise_for_status()
        return r.json()


# --------------------------------------------------------------------------- response parsing
def _speaker(raw: Any) -> Optional[str]:
    return None if raw is None else f"spk_{int(raw)}"


def _row(start_ms: int, start_s: Any, end_s: Any, text: str, speaker: Any) -> Dict[str, Any]:
    ts_ms = start_ms + int(float(start_s) * 1000)
    end_ms = start_ms + int(float(end_s) * 1000)
    return {
        "ts_ms": ts_ms,
        "end_ms": max(end_ms, ts_ms),
        "text": " ".join(str(text).split()),
        "speaker": _speaker(speaker),
        "final": True,
    }


def _words(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return results["channels"][0]["alternatives"][0].get("words") or []
    except (KeyError, IndexError, TypeError):
        return []


def _segments_from_words(results: Dict[str, Any], start_ms: int) -> List[Dict[str, Any]]:
    """Fallback when `utterances` is absent: group consecutive words by speaker, breaking on a
    pause longer than SEGMENT_GAP_MS. Depends only on the response, so it is deterministic."""
    groups: List[Dict[str, Any]] = []
    for w in _words(results):
        speaker = w.get("speaker")
        start = float(w.get("start", 0.0))
        end = float(w.get("end", start))
        token = w.get("punctuated_word") or w.get("word") or ""
        cur = groups[-1] if groups else None
        if (cur is not None and speaker == cur["speaker"]
                and (start - cur["end_s"]) * 1000 <= SEGMENT_GAP_MS):
            cur["tokens"].append(token)
            cur["end_s"] = end
        else:
            groups.append({"speaker": speaker, "start_s": start, "end_s": end,
                           "tokens": [token]})
    return [_row(start_ms, g["start_s"], g["end_s"], " ".join(g["tokens"]), g["speaker"])
            for g in groups]


def segments_from_response(response: Dict[str, Any], start_ms: int) -> List[Dict[str, Any]]:
    """Deepgram response -> transcript.jsonl rows, FINAL segments only.

    Interim segments are dropped on purpose: the legacy summary builder let interim and final
    phrases both reach the prompt, which duplicated content inside the context window.

    Timestamps are absolutised against the capture start, never against wall-clock at parse
    time, so re-running enrichment on another machine yields the same rows.
    """
    results = (response or {}).get("results") or {}
    utterances = results.get("utterances") or []
    if utterances:
        rows = [_row(start_ms, u.get("start", 0.0), u.get("end", u.get("start", 0.0)),
                     u.get("transcript", ""), u.get("speaker"))
                for u in utterances]
    else:
        rows = _segments_from_words(results, start_ms)
    return [r for r in rows if r["text"]]
