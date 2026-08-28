"""The event contract.

One normalized, totally-ordered stream. Chat, speech and vision all become events, so the
workflow never special-cases a modality and replay is a pure function of the fixture.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Literal, Optional

EventType = Literal["chat_message", "transcript_segment", "frame_caption"]


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    type: EventType
    ts_ms: int
    payload: Dict[str, Any]
    source: str = "fixture"
    final: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)

    # convenience accessors -------------------------------------------------
    @property
    def text(self) -> str:
        return str(self.payload.get("text", ""))

    @property
    def author(self) -> Optional[str]:
        return self.payload.get("author")

    @property
    def end_ms(self) -> int:
        return int(self.payload.get("end_ms", self.ts_ms))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def sort_key(e: Event) -> tuple:
    """Total order. NEVER order on insertion, wall-clock arrival, or an opaque uuid.

    The legacy `save_reasons` advanced its cursor with `message_id > last_message_id`,
    a lexicographic comparison over Twitch UUIDs, which silently skipped and reordered work.
    """
    return (e.ts_ms, e.type, e.event_id)


def order(events: Iterable[Event]) -> List[Event]:
    return sorted(events, key=sort_key)


def window(events: Iterable[Event], start_ms: int, end_ms: int,
           types: Optional[Iterable[str]] = None, final_only: bool = False) -> List[Event]:
    """Half-open [start_ms, end_ms). Deterministic and inclusive of ordering."""
    want = set(types) if types else None
    out = [
        e for e in events
        if start_ms <= e.ts_ms < end_ms
        and (want is None or e.type in want)
        and (not final_only or e.final)
    ]
    return order(out)


def make_event_id(prefix: str, ts_ms: int, discriminator: str) -> str:
    """Stable id derived from fixture content, never from wall-clock time.

    The legacy frame pipeline named frames with `now_ms()` at rename time, so ids differed on
    every machine and the unique index on (broadcaster, time_ms) behaved differently per run.
    """
    h = hashlib.sha256(f"{ts_ms}|{discriminator}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


class EventIndex:
    """Random access by id plus ordered iteration. Used by the provenance gate."""

    def __init__(self, events: Iterable[Event]) -> None:
        self._ordered: List[Event] = order(events)
        self._by_id: Dict[str, Event] = {e.event_id: e for e in self._ordered}
        if len(self._by_id) != len(self._ordered):
            raise ValueError("duplicate event_id in fixture")

    def __len__(self) -> int:
        return len(self._ordered)

    def __iter__(self):
        return iter(self._ordered)

    def get(self, event_id: str) -> Optional[Event]:
        return self._by_id.get(event_id)

    def has(self, event_id: str) -> bool:
        return event_id in self._by_id

    @property
    def events(self) -> List[Event]:
        return list(self._ordered)

    @property
    def start_ms(self) -> int:
        return self._ordered[0].ts_ms if self._ordered else 0

    @property
    def end_ms(self) -> int:
        return self._ordered[-1].ts_ms if self._ordered else 0

    def window(self, start_ms: int, end_ms: int, types=None, final_only: bool = False) -> List[Event]:
        return window(self._ordered, start_ms, end_ms, types, final_only)
