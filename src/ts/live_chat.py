"""Tier 0 live: a real broadcast's chat, grouped, with no key, no model and no cost.

This is the honest half of "live". `live.py` runs the whole pipeline against a live channel and
spends money doing it — audio, vision, the agent. This spends nothing, because everything it
shows is deterministic: anonymous Twitch IRC needs no credential (`justinfan` / `PASS
SCHMOOPIIE`, proven across 13 captures), and the grouping, the rail and the questions are
arithmetic over messages.

What Tier 0 therefore CANNOT do, and says so on screen rather than implying otherwise: there is
no transcript and no frame captions, so no group has a cause and every row is unattributed. That
is not a degraded board — it is the board telling the truth about a chat-only input, which is the
same argument the chat-only ablation makes in the evaluation.

Nothing here is written to disk. A live session leaves no fixture, no cache entry and no
trajectory, so it cannot contaminate anything a judge reproduces.
"""
from __future__ import annotations

import asyncio
import queue
import random
import threading
from typing import Any, Dict, Iterator, List, Optional

from .events import Event, EventIndex
from .ingest.capture import TWITCH_WS, parse_privmsg, pseudonym
from .report.board import grouped_summary, questions, rail
from .workflow.reduce import group_chat

TIER0_MAX_SECONDS = 600        # an unattended demo does not hold a socket open all night
TICK_SECONDS = 2.0             # the same cadence the replay board recounts at
TRAILING_MS = 60_000           # the same trailing span, so live and replay mean the same thing
MAX_LIVE_GROUPS = 6
RECV_TIMEOUT_S = 30
# How long a silent channel waits before the page says so. Anonymous IRC joins an offline channel
# perfectly happily and then delivers nothing, so "connected" followed by an empty feed is
# indistinguishable from a broken page — which is what it looks like on camera.
QUIET_AFTER_S = 12


def _pump(channel: str, out: "queue.Queue", stop: threading.Event) -> None:
    """Read anonymous IRC on a background thread and post parsed messages to the queue.

    A thread rather than an async server: the report server is a `ThreadingHTTPServer` and its
    handlers are synchronous, so the generator below stays a plain generator and the socket lives
    somewhere it can be abandoned when the browser goes away.
    """
    async def run() -> None:
        import websockets  # noqa: PLC0415 - optional at import time, see session()

        nick = f"justinfan{random.randint(10_000, 99_999)}"
        async with websockets.connect(TWITCH_WS) as ws:
            await ws.send("PASS SCHMOOPIIE")
            await ws.send(f"NICK {nick}")
            await ws.send("CAP REQ :twitch.tv/tags")
            await ws.send(f"JOIN #{channel}")
            out.put({"kind": "joined"})
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT_S)
                except asyncio.TimeoutError:
                    continue
                message = raw.decode() if isinstance(raw, bytes) else raw
                for line in message.split("\r\n"):
                    if not line:
                        continue
                    if line.startswith("PING"):
                        await ws.send("PONG :tmi.twitch.tv")
                        continue
                    row = parse_privmsg(line)
                    if row is not None:
                        out.put({"kind": "chat", "row": row})

    try:
        asyncio.run(run())
    except Exception as exc:                       # noqa: BLE001 - a demo must not crash
        out.put({"kind": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        out.put({"kind": "closed"})


def _snapshot(events: List[Event], now_ms: int) -> Dict[str, Any]:
    """Groups and rail over the trailing minute, computed exactly as replay computes them."""
    index = EventIndex(events)
    start = max(0, now_ms - TRAILING_MS)
    trailing = index.window(start + 1, now_ms + 1, types=["chat_message"])
    groups = group_chat(trailing)
    return {
        "groups": [g.to_dict() for g in groups[:MAX_LIVE_GROUPS]],
        "summary": grouped_summary(trailing, groups),
        "rail": rail(index, start + 1, now_ms + 1),
        "questions": questions(index.window(0, now_ms + 1, types=["chat_message"])),
    }


def session(channel: str, *, max_seconds: int = TIER0_MAX_SECONDS,
            tick_seconds: float = TICK_SECONDS, clock=None) -> Iterator[Dict[str, Any]]:
    """Yield `status`, `chat` and `tick` events for a live channel. Free, keyless, model-free.

    A generator, so a browser that navigates away ends the session simply by stopping asking.
    """
    import time as _time
    now = clock or _time.monotonic

    try:
        import websockets  # noqa: F401,PLC0415
    except ImportError:
        yield {"kind": "stopped", "reason": "dependency",
               "message": ("Live chat needs the `websockets` package: pip install -r "
                           "requirements.txt. Replay is unaffected and needs nothing.")}
        return

    salt = _live_salt()
    inbox: "queue.Queue" = queue.Queue()
    stop = threading.Event()
    thread = threading.Thread(target=_pump, args=(channel, inbox, stop), daemon=True)
    thread.start()

    yield {"kind": "status", "mode": "live", "tier": 0, "channel": channel,
           "cost_usd": 0.0,
           "message": (f"Connected to #{channel} over anonymous IRC. No key, no model call, no "
                       f"cost. There is no audio and no video on this tier, so nothing here has "
                       f"a cause — every group is unattributed, and that is the truth about a "
                       f"chat-only input rather than a missing feature.")}

    events: List[Event] = []
    seen = set()
    started = now()
    next_tick = started + tick_seconds
    quiet_said = False
    try:
        while now() - started < max_seconds:
            try:
                item = inbox.get(timeout=0.25)
            except queue.Empty:
                item = None

            if item and item["kind"] == "error":
                yield {"kind": "stopped", "reason": "error", "message": item["message"]}
                return
            if item and item["kind"] == "closed":
                yield {"kind": "stopped", "reason": "disconnected",
                       "message": f"#{channel} disconnected."}
                return
            if item and item["kind"] == "chat":
                row = item["row"]
                # Pseudonymised even though nothing is written down. A demo gets filmed, and a
                # real viewer's login does not belong in a submission video.
                author = pseudonym(row["login"], salt)
                if row["id"] not in seen:
                    seen.add(row["id"])
                    events.append(Event(row["id"], "chat_message", row["ts_ms"],
                                        {"text": row["text"], "author": author}))
                    yield {"kind": "chat", "id": row["id"], "author": author,
                           "text": row["text"], "ts_ms": row["ts_ms"]}

            # A channel that has said nothing since we joined is almost certainly offline. Say
            # that, once, rather than leaving a connected-but-empty feed to be read as a fault.
            if not events and not quiet_said and now() - started > QUIET_AFTER_S:
                quiet_said = True
                yield {"kind": "status", "state": "quiet", "channel": channel, "cost_usd": 0.0,
                       "message": (f"Connected to #{channel}, and it has sent nothing in "
                                   f"{QUIET_AFTER_S} seconds. The channel is probably offline — "
                                   f"anonymous IRC joins either way. Try one that is "
                                   f"broadcasting.")}

            if now() >= next_tick:
                next_tick = now() + tick_seconds
                if events:
                    snap = _snapshot(events, events[-1].ts_ms)
                    yield {"kind": "tick", "messages": len(events), **snap}

        yield {"kind": "stopped", "reason": "time_limit",
               "message": f"Live chat stopped after {max_seconds // 60} minutes, as designed."}
    finally:
        stop.set()


def _live_salt() -> str:
    """A salt for this session only, never persisted.

    `ingest.capture._salt()` reads or creates `.capture_salt`, which exists so a recorded fixture
    keeps stable pseudonyms across runs. Nothing here is recorded, so there is nothing to keep
    stable — and a live path that writes to a file the guardrails forbid committing is a trap.
    """
    return "%032x" % random.getrandbits(128)
