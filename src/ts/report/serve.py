"""Local viewer over replay output.

Read-only, bound to loopback, no keys and no upstream calls. It serves what `make replay`
already wrote to disk and never runs the agent itself, so what appears on screen is exactly the
file a judge can open and diff.

The dashboard proper is a later step. Until `static/index.html` exists this serves a plainly
labelled placeholder: the legacy shell fabricated names, emotes and cluster values and rendered
them as real output, which is an integrity-gate failure, not a cosmetic one.
"""
from __future__ import annotations

import json
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ingest.replay import load_fixture, load_meta
from ..provenance import UNKNOWN
from .board import board, rail
from .board import windows as window_tiles
from .poll import attach_drafts

STATIC = Path(__file__).parent / "static"
ROUTES = ["/", "/method", "/api/replay", "/api/fixtures",
          "/api/stream?fixture=<id>&system=<agent|baseline>&speed=<1|4|8>",
          "/api/board?fixture=<id>&window=<n>",
          "/api/live?channel=<name>", "/api/budget", "/philosophy",
          "/static/<file>"]

PLACEHOLDER = """<!doctype html>
<meta charset="utf-8"><title>Twitch Agent — replay output</title>
<body style="font-family:system-ui;font-weight:300;max-width:44rem;margin:4rem auto;color:#292524">
<h1 style="font-weight:300">Replay output</h1>
<p><strong>This is not the dashboard.</strong> The interface has not been built yet. This page
exists so that <code>make demo</code> serves something truthful instead of nothing.</p>
<p>The verified cards for this fixture are served raw at
<a href="/api/replay">/api/replay</a>, and the baseline at
<a href="/api/replay?system=baseline">/api/replay?system=baseline</a>.</p>
</body>
"""


def result_path(out_dir: Path | str, fixture_id: str, system: str = "agent") -> Path:
    return Path(out_dir) / f"{fixture_id}.{system}.json"


def cited_events(result: Dict[str, Any], fixture: Path | str) -> Dict[str, Any]:
    """Only the events the cards actually cite.

    The evidence drawer needs the message text behind an id; the browser has no business holding
    a whole fixture. An id that a card cited but the fixture does not contain is simply absent
    here, and the drawer renders it as missing — which is the provenance gate made visible.
    """
    ids = set()
    for window in result.get("windows") or []:
        for card in list(window.get("verified") or []) + list(window.get("rejected") or []):
            ids.update(card.get("evidence") or [])
            trigger_id = (card.get("trigger") or {}).get("event_id")
            if trigger_id and trigger_id != UNKNOWN:
                ids.add(trigger_id)
    if not ids:
        return {}

    index = load_fixture(fixture)
    out = {}
    for event_id in sorted(ids):
        event = index.get(event_id)
        if event is not None:
            out[event_id] = {"type": event.type, "ts_ms": event.ts_ms,
                             "text": event.text, "author": event.author}
    return out


def payload(fixture: Path | str, out_dir: Path | str, system: str = "agent") -> Dict[str, Any]:
    """Fixture metadata plus the recorded run. Missing output is an actionable error, never an
    empty page that looks like a run with no signals."""
    meta = load_meta(fixture)
    fixture_id = meta.get("fixture_id") or Path(fixture).name
    path = result_path(out_dir, fixture_id, system)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run `make replay FIXTURE={fixture}` "
            f"(or `make baseline`) before serving."
        )
    result = json.loads(path.read_text(encoding="utf-8"))

    # Built here rather than in the browser: what a streamer approves has to be derived
    # deterministically from verified evidence, and that belongs somewhere testable.
    for window in result.get("windows") or []:
        attach_drafts(window.get("verified") or [])

    return {"meta": meta, "result": result, "events": cited_events(result, fixture),
            "evaluation": evaluation(out_dir),
            "hero": hero(Path(fixture).parent, out_dir)}


# The hero makes the product's argument, so it is pinned to the window where the argument is
# provable rather than to whatever fixture happens to be loaded. On this capture nobody is
# speaking — Deepgram returned zero utterances for the whole 12 minutes — chat is typing guesses
# at an on-screen word game, and the only possible cause is the frame. Everything below the fold
# still follows the loaded fixture.
HERO_FIXTURE = "stableronaldo_2026-08-30T0723"


def _grounded(card: Dict[str, Any]) -> bool:
    """A card that actually shows a cause: gate-clean, not an abstention, naming a real event
    with a verbatim quote. Anything less is not evidence of the thesis."""
    trigger = card.get("trigger") or {}
    return bool(
        (card.get("gate") or {}).get("ok")
        and card.get("type") not in (None, "none")
        and trigger.get("event_id") not in (None, "", "unknown")
        and trigger.get("quote")
        and card.get("evidence")
    )


def _lead_up_to(chat, cited, span: int = 12):
    """The last `span` messages ending on the first cited one, so the freeze is the payoff."""
    stop = next((i for i, e in enumerate(chat) if e.event_id in cited), None)
    window = chat[max(0, stop - span + 1):stop + 1] if stop is not None else chat[:span]
    return [{"id": e.event_id, "text": e.text, "cited": e.event_id in cited} for e in window]


def hero(fixtures_root: Path | str, out_dir: Path | str) -> Optional[Dict[str, Any]]:
    """One grounded card from a recorded run, with the real chat around it.

    Deliberately one card and not three. The page previously showed three cards reading "Chat
    mention of X" over the line "caused by unknown unknown" — echoes, not signals, under a
    headline about causation. One card that names its cause is worth more than three that do not,
    and if none exists this returns None and the stage does not render.

    Screen triggers are preferred because they are the argument a chat-only system cannot make.
    """
    root, out = Path(fixtures_root), Path(out_dir)
    fixture_dir = root / HERO_FIXTURE
    if not fixture_dir.exists():
        return None

    found = []
    for system in ("agent", "baseline"):
        path = result_path(out, HERO_FIXTURE, system)
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for window in doc.get("windows") or []:
            for card in window.get("verified") or []:
                if _grounded(card):
                    found.append((system, window.get("window_ms"), card))
    if not found:
        return None

    # deterministic: screen triggers first, then earliest window, then card id
    found.sort(key=lambda f: ((f[2].get("trigger") or {}).get("kind") != "screen",
                              f[1][0] if f[1] else 0, str(f[2].get("signal_id"))))
    system, window_ms, card = found[0]

    index = load_fixture(fixture_dir)
    start, end = window_ms
    chat = [e for e in index.window(start, end, types=["chat_message"])]
    cited = set(card.get("evidence") or [])
    trigger_id = (card.get("trigger") or {}).get("event_id")
    trigger_event = index.get(trigger_id)

    return {
        "system": system,
        "fixture_id": HERO_FIXTURE,
        "window_ms": window_ms,
        "card": card,
        "speech_in_window": len(index.window(start, end, types=["transcript_segment"])),
        "trigger": {"id": trigger_id, "ts_ms": trigger_event.ts_ms if trigger_event else None,
                    "text": trigger_event.text if trigger_event else None},
        # Real messages, in order, ending on the one the card cites — the stream has to arrive
        # AT the frozen message, so it is built backwards from the citation rather than taken
        # from the top of the window. Taking the first N left the freeze off the end entirely.
        "stream": _lead_up_to(chat, cited),
        "cited": [{"id": i, "text": index.get(i).text} for i in card.get("evidence") or []
                  if index.get(i)],
    }


def available(fixtures_root: Path | str, out_dir: Path | str) -> List[Dict[str, Any]]:
    """Fixtures a judge can actually switch to: enriched, and with a recorded run to show.

    This is a picker over RECORDED WINDOWS, not live capture. Nothing here starts a stream, and
    the UI has to say so — a picker that looks live would be claiming a capability the judge
    cannot verify and that costs money to exercise.
    """
    root, out = Path(fixtures_root), Path(out_dir)
    if not root.is_dir():
        return []
    found = []
    for d in sorted(root.iterdir()):
        if not (d / "meta.json").is_file():
            continue
        meta = load_meta(d)
        fixture_id = meta.get("fixture_id") or d.name
        systems = [s for s in ("agent", "baseline") if result_path(out, fixture_id, s).exists()]
        if not systems or not meta.get("enriched"):
            continue
        found.append({
            "fixture_id": fixture_id,
            "channel": meta.get("channel"),
            "captured_utc": meta.get("captured_utc"),
            "duration_s": meta.get("duration_s"),
            "chat_messages": meta.get("chat_messages"),
            "systems": systems,
        })
    return found


# Playback speeds the UI offers. The multiplier is echoed back in the opening event so the page
# can state it: a replay that silently ran at 8x while showing "1x" would be lying about the
# cadence, which is the one thing this view claims to reproduce faithfully.
SPEEDS = (1, 4, 8)
MAX_STREAM_SECONDS = 15 * 60


def stream_events(fixture: Path | str, out_dir: Path | str, system: str = "agent"):
    """The recorded run as a time-ordered script: chat at its true offsets, cards at the moment
    the window that produced them closed.

    Reading only. No model call, no key, no cost — the cadence comes from the timestamps already
    in the fixture, so "looks live" and "is a replay" are both true at once and the badge says
    which. A window's cards are emitted at its END because that is when the agent could first
    have produced them; emitting them at the start would show the answer before the evidence.
    """
    index = load_fixture(fixture)
    chat = index.window(index.start_ms, index.end_ms + 1, types=["chat_message"])
    if not chat:
        return
    origin = chat[0].ts_ms

    script = [(e.ts_ms - origin, {"kind": "chat", "id": e.event_id, "author": e.author,
                                 "text": e.text}) for e in chat]

    meta = load_meta(fixture)
    fixture_id = meta.get("fixture_id") or Path(fixture).name
    path = result_path(Path(out_dir), fixture_id, system)
    recorded: List[Dict[str, Any]] = []
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        recorded = list(doc.get("windows") or [])
        for window in recorded:
            bounds = window.get("window_ms") or [origin, origin]
            at = max(0, bounds[1] - origin)
            for card in window.get("verified") or []:
                script.append((at, {"kind": "card", "state": _state(card), "card": card}))
            for card in window.get("rejected") or []:
                script.append((at, {"kind": "card", "state": "rejected", "card": card}))

    # The board and the rail, one per tile, emitted when the tile closes — the same instant the
    # cards for it arrive, because that is the earliest the window could be described at all.
    # Computed here rather than in the browser: the client never holds the fixture, and these
    # numbers have to be identical to what `/api/board` serves for the same window.
    seen: set = set()
    for start, end in window_tiles(index):
        chat_in = index.window(start, end, types=["chat_message"])
        if not chat_in:
            continue
        cards = [c for w in recorded
                 if start <= ((w.get("window_ms") or [0])[0]) < end
                 for c in list(w.get("verified") or []) + list(w.get("rejected") or [])]
        script.append((max(0, end - origin), {
            "kind": "board",
            "board": board(index, start, end),
            "rail": rail(index, start, end, cards=cards, seen_authors=seen),
        }))
        seen.update(e.author for e in chat_in)

    script.sort(key=lambda s: s[0])
    return script


def _state(card: Dict[str, Any]) -> str:
    if not (card.get("gate") or {}).get("ok"):
        return "rejected"
    return "grounded" if _grounded(card) else "abstained"


def evaluation(out_dir: Path | str) -> Optional[Dict[str, Any]]:
    """The measured comparison, read from what `make eval` wrote.

    Read, never recomputed: `evals/scorer.py` owns every published metric, and a rate computed a
    second time here would eventually disagree with the one in `evidence/report.md`. Returns None
    when the eval has not been run, so the editorial sections stay hidden rather than rendering
    an empty table that reads like a measured zero.
    """
    path = Path(out_dir)
    summary = path / "summary.json" if path.name != "raw-results" else path.parent / "summary.json"
    if not summary.exists():
        return None
    try:
        return json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _static_file(name: str) -> Optional[Path]:
    """Only ever a plain filename inside STATIC - no traversal, no symlink escape."""
    candidate = STATIC / Path(name).name
    return candidate if candidate.is_file() else None


class ReplayHandler(BaseHTTPRequestHandler):
    fixture: Path = Path(".")
    out_dir: Path = Path("evidence/raw-results")
    quiet: bool = False

    def _send(self, code: int, body: str, ctype: str) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, indent=1),
                   "application/json; charset=utf-8")

    def _resolve(self, params: Dict[str, str]) -> Path:
        """A fixture named in a query string is untrusted input: strip it to a bare filename and
        require it to sit beside the served one, or fall back."""
        name = Path(params.get("fixture", "") or self.fixture.name).name
        target = self.fixture.parent / name
        return target if (target / "meta.json").is_file() else self.fixture

    def _live(self, params: Dict[str, str]) -> None:
        """Live capture over the same SSE channel as replay.

        Explicitly reached and never the default: the graded path is keyless replay, and a page
        that started spending on load would put that at risk. Every event carries the running
        estimate and the ledger state, so the number on screen is the number being spent.
        """
        from ..live import session

        channel = re.sub(r"[^A-Za-z0-9_]", "", params.get("channel", ""))[:40]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def emit(event: str, data: Any) -> bool:
            try:
                self.wfile.write(
                    f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    .encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, ValueError):
                return False

        if not channel:
            emit("stopped", {"kind": "stopped", "reason": "no_channel",
                             "message": "Name a channel to go live on."})
            return
        try:
            for event in session(channel):
                if not emit(event["kind"], event):
                    return                       # navigating away ends the spending
        except Exception as exc:                 # noqa: BLE001
            emit("stopped", {"kind": "stopped", "reason": "error", "message": str(exc)})

    def _stream(self, params: Dict[str, str]) -> None:
        """Server-Sent Events: the recorded run replayed at its true cadence.

        Deliberately a replay and labelled as one. The `mode` and `speed` in the opening event
        are what the badge reads from, so the page cannot show "1x REPLAY" while the server runs
        at another rate — the cadence is the only thing this view claims, so it has to be true.
        """
        target = self._resolve(params)
        system = params.get("system", "agent")
        if system not in ("agent", "baseline"):
            system = "agent"
        try:
            speed = int(params.get("speed", "1"))
        except ValueError:
            speed = 1
        if speed not in SPEEDS:
            speed = 1

        script = stream_events(target, self.out_dir, system) or []

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(event: str, data: Any) -> bool:
            try:
                self.wfile.write(
                    f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    .encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, ValueError):
                return False   # the browser navigated away or switched channel

        meta = load_meta(target)
        # NOT named "open": EventSource reserves that for its own connection event, so a
        # custom listener would never fire and the badge could not read the mode.
        if not emit("meta", {
            "mode": "replay", "speed": speed, "system": system,
            "fixture_id": meta.get("fixture_id") or target.name,
            "channel": meta.get("channel"),
            "captured_utc": meta.get("captured_utc"),
            "total_chat": sum(1 for _, e in script if e["kind"] == "chat"),
            "total_cards": sum(1 for _, e in script if e["kind"] == "card"),
            "duration_ms": script[-1][0] if script else 0,
            # so an empty signals column can say when to expect something instead of sitting
            # blank for a minute, which reads as broken rather than pending
            "first_card_ms": next((o for o, e in script if e["kind"] == "card"), None),
        }):
            return

        started = time.monotonic()
        for offset_ms, event in script:
            due = started + (offset_ms / 1000.0) / speed
            while True:
                delay = due - time.monotonic()
                if delay <= 0:
                    break
                time.sleep(min(delay, 0.25))
                if time.monotonic() - started > MAX_STREAM_SECONDS:
                    break
            if time.monotonic() - started > MAX_STREAM_SECONDS:
                break
            if not emit(event["kind"], event):
                return
        emit("done", {"ok": True})

    def do_GET(self) -> None:  # noqa: N802 - http.server's naming
        route, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

        if route == "/api/budget":
            from ..live import budget_state
            self._json(200, budget_state())
            return

        if route == "/api/live":
            self._live(params)
            return

        if route == "/api/stream":
            self._stream(params)
            return

        if route == "/api/board":
            # A window's board and rail without waiting for the stream to reach it. The page does
            # not need this; a judge reading one window, and the tests, do.
            target = self._resolve(params)
            index = load_fixture(target)
            tiles = window_tiles(index)
            try:
                n = int(params.get("window", "0"))
            except ValueError:
                n = 0
            if not tiles or not 0 <= n < len(tiles):
                self._json(404, {"error": "no such window", "windows": len(tiles)})
                return
            start, end = tiles[n]
            self._json(200, {"fixture": target.name, "window": n, "windows": len(tiles),
                             "board": board(index, start, end),
                             "rail": rail(index, start, end)})
            return

        if route == "/api/fixtures":
            self._json(200, {"fixtures": available(self.fixture.parent, self.out_dir),
                             "selected": self.fixture.name})
            return

        if route == "/api/replay":
            # The picker may name another fixture, but only one that sits beside the served one:
            # a filename from a query string must never become a path.
            target = self._resolve(params)
            system = params.get("system", "agent")
            if system not in ("agent", "baseline"):
                system = "agent"
            try:
                self._json(200, payload(target, self.out_dir, system))
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc), "fixture": target.name, "system": system})
            return

        if route in ("/", "/index.html", "/method", "/philosophy"):
            name = {"/method": "method.html",
                    "/philosophy": "philosophy.html"}.get(route, "index.html")
            page = STATIC / name
            body = page.read_text(encoding="utf-8") if page.is_file() else PLACEHOLDER
            self._send(200, body, "text/html; charset=utf-8")
            return

        if route.startswith("/static/"):
            path = _static_file(route[len("/static/"):])
            if path is not None:
                ctype = {".css": "text/css", ".js": "text/javascript",
                         ".svg": "image/svg+xml"}.get(path.suffix, "application/octet-stream")
                self._send(200, path.read_text(encoding="utf-8"), f"{ctype}; charset=utf-8")
                return

        self._json(404, {"error": f"no route {route}", "routes": ROUTES})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        if not self.quiet:
            super().log_message(fmt, *args)


def make_server(fixture: Path | str, out_dir: Path | str, port: int,
                host: str = "127.0.0.1", quiet: bool = False) -> ThreadingHTTPServer:
    handler = type("BoundReplayHandler", (ReplayHandler,),
                   {"fixture": Path(fixture), "out_dir": Path(out_dir), "quiet": quiet})
    # ThreadingHTTPServer, not HTTPServer: an SSE connection is held open for the length of the
    # playback, and on a single-threaded server that would block every other request — the page
    # itself would never load while a stream was running.
    return ThreadingHTTPServer((host, port), handler)


def serve(fixture: Path | str, out_dir: Path | str, port: int = 8000,
          host: str = "127.0.0.1") -> int:
    httpd = make_server(fixture, out_dir, port, host)
    print(f"serving {fixture} from {out_dir} on http://{host}:{httpd.server_port}  (ctrl-c to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
    return 0
