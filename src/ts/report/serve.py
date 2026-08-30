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
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from ..ingest.replay import load_fixture, load_meta
from ..provenance import UNKNOWN
from .poll import attach_drafts

STATIC = Path(__file__).parent / "static"
ROUTES = ["/", "/api/replay", "/api/replay?system=baseline", "/static/<file>"]

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
            "evaluation": evaluation(out_dir)}


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

    def do_GET(self) -> None:  # noqa: N802 - http.server's naming
        route, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

        if route == "/api/replay":
            try:
                self._json(200, payload(self.fixture, self.out_dir,
                                        params.get("system", "agent")))
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
            return

        if route in ("/", "/index.html"):
            index = STATIC / "index.html"
            body = index.read_text(encoding="utf-8") if index.is_file() else PLACEHOLDER
            self._send(200, body, "text/html; charset=utf-8")
            return

        if route.startswith("/static/"):
            path = _static_file(route[len("/static/"):])
            if path is not None:
                ctype = {".css": "text/css", ".js": "text/javascript"}.get(
                    path.suffix, "application/octet-stream")
                self._send(200, path.read_text(encoding="utf-8"), f"{ctype}; charset=utf-8")
                return

        self._json(404, {"error": f"no route {route}", "routes": ROUTES})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        if not self.quiet:
            super().log_message(fmt, *args)


def make_server(fixture: Path | str, out_dir: Path | str, port: int,
                host: str = "127.0.0.1", quiet: bool = False) -> HTTPServer:
    handler = type("BoundReplayHandler", (ReplayHandler,),
                   {"fixture": Path(fixture), "out_dir": Path(out_dir), "quiet": quiet})
    return HTTPServer((host, port), handler)


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
