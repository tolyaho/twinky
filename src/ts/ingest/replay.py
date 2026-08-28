"""Fixture -> events. The graded path reads only this.

Fixture layout:
    meta.json          channel, start_ms, duration_ms, tool versions, provenance
    chat.jsonl         {ts_ms, id, author, text, ...}       (author already pseudonymised)
    transcript.jsonl   {ts_ms, end_ms, text, speaker, final}
    frames.jsonl       {ts_ms, caption, frame}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List

from ..events import Event, EventIndex, make_event_id


def _read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return iter(())
    def gen():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
    return gen()


def load_fixture(fixture_dir: Path | str) -> EventIndex:
    d = Path(fixture_dir)
    if not d.exists():
        raise FileNotFoundError(f"fixture not found: {d}")

    events: List[Event] = []

    for row in _read_jsonl(d / "chat.jsonl"):
        eid = row.get("id") or make_event_id("msg", row["ts_ms"], row.get("text", ""))
        events.append(Event(
            event_id=eid, type="chat_message", ts_ms=int(row["ts_ms"]),
            payload={"text": row.get("text", ""), "author": row.get("author")},
            meta={k: v for k, v in row.items() if k not in {"id", "ts_ms", "text", "author"}},
        ))

    for row in _read_jsonl(d / "transcript.jsonl"):
        # final_only filtering happens at query time; interim segments must never silently
        # enter a prompt, which is exactly what the legacy summary builder did.
        eid = row.get("id") or make_event_id("tr", row["ts_ms"], row.get("text", ""))
        events.append(Event(
            event_id=eid, type="transcript_segment", ts_ms=int(row["ts_ms"]),
            payload={"text": row.get("text", ""), "end_ms": int(row.get("end_ms", row["ts_ms"])),
                     "speaker": row.get("speaker")},
            final=bool(row.get("final", True)),
        ))

    for row in _read_jsonl(d / "frames.jsonl"):
        eid = row.get("id") or make_event_id("frm", row["ts_ms"], row.get("caption", ""))
        events.append(Event(
            event_id=eid, type="frame_caption", ts_ms=int(row["ts_ms"]),
            payload={"text": row.get("caption", ""), "frame": row.get("frame")},
        ))

    return EventIndex(events)


def load_meta(fixture_dir: Path | str) -> Dict[str, Any]:
    p = Path(fixture_dir) / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
