"""The server must survive a client that disappears mid-stream.

Reported as: clicking a channel chip and a speed button in quick succession killed the `make
demo` process, after which `/api/fixtures` failed too. It does not reproduce on the current
build — twelve abrupt socket resets mid-stream leave the server healthy — and the most likely
reason is the switch to `ThreadingHTTPServer`, made in a different iteration to stop an SSE
connection blocking page loads. On the single-threaded server an SSE write to a dead socket
would take out `serve_forever`'s only thread, which is exactly "the process was gone".

That makes this a regression test rather than a fix: the property was restored by accident and
is now pinned on purpose.
"""
import socket
import threading
import time
import urllib.request

import pytest

from ts.report import serve as serve_mod

FIXTURE = "evals/fixtures/sample"


@pytest.fixture
def server(tmp_path):
    from pathlib import Path
    httpd = serve_mod.make_server(Path(FIXTURE), tmp_path, port=0, quiet=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def _drop_after_first_event(base, path):
    """Read a little, then reset the connection hard — a browser navigating away, not a clean
    close. `SO_LINGER` with a zero timeout sends RST instead of FIN."""
    host, port = base.split("//")[1].split(":")
    s = socket.create_connection((host, int(port)), timeout=5)
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
    try:
        s.recv(64)
    except OSError:
        pass
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
    s.close()


def test_the_server_survives_a_client_dropping_mid_stream(server):
    _drop_after_first_event(server, "/api/stream?speed=8")
    time.sleep(0.4)

    with urllib.request.urlopen(f"{server}/api/fixtures", timeout=5) as r:
        assert r.status == 200


def test_the_server_survives_many_overlapping_drops(server):
    """Two clicks in the same second open two streams and abandon the first. Six at once is the
    same shape with less patience."""
    threads = [threading.Thread(target=_drop_after_first_event,
                                args=(server, "/api/stream?speed=8"))
               for _ in range(6)]
    for t in threads:
        t.start()
        time.sleep(0.02)
    for t in threads:
        t.join()
    time.sleep(0.5)

    with urllib.request.urlopen(f"{server}/api/fixtures", timeout=5) as r:
        assert r.status == 200
    with urllib.request.urlopen(f"{server}/", timeout=5) as r:
        assert r.status == 200


def test_a_page_still_loads_while_a_stream_is_open(server):
    """The reason the server is threaded: an SSE connection is held for the whole playback."""
    holder = threading.Thread(
        target=lambda: urllib.request.urlopen(f"{server}/api/stream?speed=1", timeout=3).read(64),
        daemon=True)
    holder.start()
    time.sleep(0.3)

    with urllib.request.urlopen(f"{server}/", timeout=5) as r:
        assert r.status == 200


def test_the_server_is_threaded():
    serve = (serve_mod.STATIC.parent / "serve.py").read_text(encoding="utf-8")
    assert "ThreadingHTTPServer((host, port), handler)" in serve
