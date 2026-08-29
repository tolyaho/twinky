"""Bounded context tools.

The agent chooses what context it needs; the controller - not the model - enforces schemas,
window sizes and ordering. Windows are bounded by TIME, never by the model's context limit.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..events import EventIndex
from .reduce import reduce_chat


class Tools:
    def __init__(self, index: EventIndex, *, max_window_ms: int = 180_000) -> None:
        self.index = index
        self.max_window_ms = max_window_ms
        self.calls: List[Dict[str, Any]] = []

    def _guard(self, start_ms: int, end_ms: int) -> None:
        if end_ms < start_ms:
            raise ValueError("end before start")
        if end_ms - start_ms > self.max_window_ms:
            raise ValueError(f"window {end_ms - start_ms}ms exceeds cap {self.max_window_ms}ms")

    def get_chat_window(self, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
        self._guard(start_ms, end_ms)
        evs = self.index.window(start_ms, end_ms, types=["chat_message"])
        self.calls.append({"tool": "get_chat_window", "args": {"start_ms": start_ms, "end_ms": end_ms},
                           "n": len(evs)})
        return [{"id": e.event_id, "ts_ms": e.ts_ms, "author": e.author, "text": e.text} for e in evs]

    def get_transcript_window(self, start_ms: int, end_ms: int, final_only: bool = True) -> List[Dict[str, Any]]:
        """final_only defaults True. The legacy summary builder omitted this filter, so interim
        and final phrases both entered context and duplicated content."""
        self._guard(start_ms, end_ms)
        evs = self.index.window(start_ms, end_ms, types=["transcript_segment"], final_only=final_only)
        self.calls.append({"tool": "get_transcript_window",
                           "args": {"start_ms": start_ms, "end_ms": end_ms, "final_only": final_only},
                           "n": len(evs)})
        return [{"id": e.event_id, "ts_ms": e.ts_ms, "end_ms": e.end_ms,
                 "speaker": e.payload.get("speaker"), "text": e.text} for e in evs]

    def get_frame_captions(self, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
        self._guard(start_ms, end_ms)
        evs = self.index.window(start_ms, end_ms, types=["frame_caption"])
        self.calls.append({"tool": "get_frame_captions", "args": {"start_ms": start_ms, "end_ms": end_ms},
                           "n": len(evs)})
        return [{"id": e.event_id, "ts_ms": e.ts_ms, "caption": e.text} for e in evs]

    def group_repeated(self, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
        self._guard(start_ms, end_ms)
        evs = self.index.window(start_ms, end_ms, types=["chat_message"])
        bursts = reduce_chat(evs)
        self.calls.append({"tool": "group_repeated", "args": {"start_ms": start_ms, "end_ms": end_ms},
                           "n": len(bursts)})
        return [b.to_dict() for b in bursts]
