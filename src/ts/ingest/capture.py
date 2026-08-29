"""Stage 1 of fixture creation: RAW CAPTURE. **No API keys required.**

Splitting capture from enrichment matters because capture is the irreversible step - a stream
that is live now will not be live later - while enrichment (STT, vision) can happen any time
afterwards from the recorded bytes.

    python -m ts.cli capture --channel NAME --minutes 10

Writes:
    <out>/<channel>_<utc>/raw/chat.jsonl      Twitch IRC, anonymous connection
    <out>/<channel>_<utc>/raw/audio.wav       16 kHz mono s16le
    <out>/<channel>_<utc>/raw/frames/*.jpg    one frame per `interval` seconds
    <out>/<channel>_<utc>/meta.json

Chatter logins are pseudonymised AT CAPTURE TIME - a real username never touches disk. The salt
lives in `.capture_salt` (gitignored) so pseudonyms stay stable across fixtures on this machine
and cannot be reversed by anyone who receives the fixture.

NOTE: the network boundary is untested here - no Twitch egress in this environment. Everything
below it is covered: frame stamping, retry safety, the ffmpeg failure path, the empty-capture
guard, and the capture -> enrich -> load_fixture seam. So a failure on first contact should mean
streamlink, ffmpeg or the channel, not this module. Still run it once on a 60-second segment and
check `make inspect` before committing to three full captures.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("capture")

# ffmpeg's own output pattern, `%06d.jpg`. Anything else in the directory was already stamped.
SEQUENTIAL_FRAME = re.compile(r"^\d{6}\.jpg$")

# A WAV header alone is 44 bytes; anything at or under this captured no audio at all.
MIN_AUDIO_BYTES = 1024

TWITCH_WS = "wss://irc-ws.chat.twitch.tv:443"
SALT_FILE = Path(".capture_salt")


def _salt() -> str:
    if not SALT_FILE.exists():
        SALT_FILE.write_text(secrets.token_hex(16), encoding="utf-8")
    return SALT_FILE.read_text(encoding="utf-8").strip()


def pseudonym(login: str, salt: str) -> str:
    """Stable, one-way. Real logins never reach the fixture."""
    return "u_" + hashlib.sha256(f"{salt}|{login.lower()}".encode()).hexdigest()[:10]


# --------------------------------------------------------------------------- chat
def parse_privmsg(line: str) -> Optional[Dict[str, Any]]:
    """Parse one tagged PRIVMSG. Ported from the legacy parser, with the bugs removed:
    no `message_reply_id` written to a field that does not exist, and the timestamp comes
    from Twitch's own `tmi-sent-ts` rather than local arrival time."""
    if "PRIVMSG" not in line or not line.startswith("@"):
        return None
    sp = line.find(" ")
    if sp == -1:
        return None
    try:
        tags = dict(t.split("=", 1) for t in line[1:sp].split(";") if t)
    except ValueError:
        return None

    mid, ts = tags.get("id"), tags.get("tmi-sent-ts")
    if not mid or not ts:
        return None

    rest = line[sp + 1:]
    if not rest.startswith(":"):
        return None
    body = rest[1:]
    colon = body.find(":")
    if colon == -1:
        return None

    return {
        "id": mid,
        "ts_ms": int(ts),
        "login": (tags.get("display-name") or "").lower(),
        "text": body[colon + 1:].rstrip("\r\n"),
        "user_type": tags.get("user-type") or "",
        "room_id": tags.get("room-id"),
        "reply_to": tags.get("reply-parent-msg-id") or None,
    }


async def capture_chat(channel: str, out: Path, stop: asyncio.Event, salt: str) -> int:
    import websockets  # noqa: PLC0415

    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        while not stop.is_set():
            try:
                nick = f"justinfan{random.randint(10_000, 99_999)}"
                async with websockets.connect(TWITCH_WS) as ws:
                    await ws.send("PASS SCHMOOPIIE")
                    await ws.send(f"NICK {nick}")
                    await ws.send("CAP REQ :twitch.tv/tags")
                    await ws.send(f"JOIN #{channel}")
                    logger.info("chat connected: #%s", channel)

                    while not stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = raw.decode() if isinstance(raw, bytes) else raw
                        for line in msg.split("\r\n"):
                            if not line:
                                continue
                            if line.startswith("PING"):
                                await ws.send("PONG :tmi.twitch.tv")
                                continue
                            row = parse_privmsg(line)
                            if row is None:
                                continue
                            fh.write(json.dumps({
                                "id": row["id"], "ts_ms": row["ts_ms"],
                                "author": pseudonym(row["login"], salt),
                                "text": row["text"], "user_type": row["user_type"],
                            }, ensure_ascii=False) + "\n")
                            fh.flush()
                            n += 1
            except asyncio.TimeoutError:
                continue
            except Exception as exc:  # noqa: BLE001
                if stop.is_set():
                    break
                logger.warning("chat reconnect after %r", exc)
                await asyncio.sleep(3)
    return n


# --------------------------------------------------------------------------- media
def _open_stream(channel: str, prefer: list[str]):
    import streamlink  # noqa: PLC0415
    streams = streamlink.Streamlink().streams(f"https://www.twitch.tv/{channel}")
    for name in prefer:
        if name in streams:
            logger.info("selected quality %r", name)
            return streams[name], name
    raise RuntimeError(f"no usable stream for {channel!r} - is the channel live?")


def stamp_frames(frames_dir: Path, start_ms: int, interval: int) -> int:
    """Rename ffmpeg's sequential frames to their ABSOLUTE capture timestamp in ms.

    Replay then never has to guess and never depends on wall-clock at load time — the legacy
    pipeline named frames with `now_ms()` at rename time, so ids differed on every machine.

    Only `%06d.jpg` names are touched. A frame already carrying a timestamp is left alone: a
    second pass over the same directory would otherwise renumber it from zero against a new
    `start_ms`, and capture is exactly the step that gets retried after it fails.
    """
    sequential = sorted(p for p in frames_dir.glob("*.jpg") if SEQUENTIAL_FRAME.match(p.name))
    for i, path in enumerate(sequential):
        path.rename(frames_dir / f"{start_ms + i * interval * 1000}.jpg")
    return len(sequential)


def capture_media(channel: str, root: Path, seconds: int, interval: int = 30) -> Dict[str, Any]:
    """streamlink -> ffmpeg, producing audio.wav and frames/*.jpg in one pass."""
    frames_dir = root / "raw" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    audio_path = root / "raw" / "audio.wav"

    stale = list(frames_dir.glob("*.jpg"))
    if stale:
        raise RuntimeError(
            f"{frames_dir} already holds {len(stale)} frames. Capture writes a fresh fixture; "
            "re-running into a used directory would stamp old frames with a new start time. "
            "Move or delete the directory and start again."
        )

    stream, quality = _open_stream(channel, ["480p", "360p", "720p60", "720p", "best"])
    start_ms = int(time.time() * 1000)

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin",
        "-fflags", "+nobuffer", "-i", "pipe:0",
        "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-f", "wav", str(audio_path),
        "-map", "0:v:0", "-vf", f"fps=1/{interval},scale=-1:720", "-fps_mode", "vfr",
        str(frames_dir / "%06d.jpg"),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    deadline = time.time() + seconds
    try:
        with stream.open() as fd:
            try:
                while time.time() < deadline:
                    chunk = fd.read(8192)
                    if not chunk:
                        break
                    proc.stdin.write(chunk)
            except BrokenPipeError as exc:
                proc.poll()
                err = b""
                if proc.stderr is not None:
                    try:
                        err = proc.stderr.read() or b""
                    except Exception:
                        pass
                raise RuntimeError(
                    f"ffmpeg exited early (rc={proc.returncode}). stderr:\n"
                    + err.decode("utf-8", "replace").strip()
                ) from exc
    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        proc.wait(timeout=30)

    if proc.returncode not in (0, None):
        stderr = (proc.stderr.read().decode("utf-8", "replace")[-2000:]
                  if proc.stderr else "")
        raise RuntimeError(f"ffmpeg exited {proc.returncode} while capturing {channel!r}:\n{stderr}")

    renamed = stamp_frames(frames_dir, start_ms, interval)

    # A capture that produced nothing must fail here, not silently write a meta.json that
    # declares success. The alternative is discovering it at enrichment time, hours later,
    # with the broadcast over.
    audio_bytes = audio_path.stat().st_size if audio_path.exists() else 0
    if renamed == 0 or audio_bytes < MIN_AUDIO_BYTES:
        raise RuntimeError(
            f"capture of {channel!r} produced {renamed} frames and {audio_bytes} bytes of audio. "
            "Check that the channel is live, that ffmpeg is on PATH, and that streamlink can "
            "reach Twitch, then run again against a fresh directory."
        )

    return {"quality": quality, "start_ms": start_ms, "frames": renamed,
            "audio": str(audio_path.relative_to(root)), "frame_interval_s": interval}


# --------------------------------------------------------------------------- driver
async def capture(channel: str, minutes: int, out_dir: Path, interval: int = 30) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M")
    root = Path(out_dir) / f"{channel}_{stamp}"
    (root / "raw").mkdir(parents=True, exist_ok=True)
    salt = _salt()

    stop = asyncio.Event()
    chat_task = asyncio.create_task(capture_chat(channel, root / "raw" / "chat.jsonl", stop, salt))
    media = await asyncio.to_thread(capture_media, channel, root, minutes * 60, interval)
    stop.set()
    n_chat = await chat_task

    (root / "meta.json").write_text(json.dumps({
        "fixture_id": root.name, "channel": channel,
        "captured_utc": stamp, "duration_s": minutes * 60,
        "chat_messages": n_chat, "pseudonymised": True,
        "enriched": False,
        "provenance": "Captured from a public Twitch broadcast. Chatter logins pseudonymised at "
                      "capture time with a local salt that is not distributed. Raw audio is not "
                      "committed; only the derived transcript is.",
        **media,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    logger.info("captured %s: %d chat messages, %d frames", root.name, n_chat, media["frames"])
    return root
