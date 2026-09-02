#!/usr/bin/env python3
"""Press stills of the real dashboard — one window, one channel, one run.

Every frame here is the actual page under a real browser. Nothing is composited, nothing is
mocked, no number is retouched.

    # 1. serve the page (separate terminal, leave it running)
    make demo FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723

    # 2. shoot
    .venv/bin/python scripts/press_shots.py
    .venv/bin/python scripts/press_shots.py --list

Four stills come off a single continuous playback of one channel, in one browser context at one
viewport, so the chrome, the type size and the column positions are identical across the set and
the interface does not jump between frames. A fifth is a second pass on `marlon`, because the
`you said` pill cannot exist on a silent stream and `stableronaldo` is one.

**Shots wait on the page's state, never on a stopwatch.** The board is redrawn per 60-second
window rather than accumulated, so "the board is grouping" is a property of the window on screen,
not of a moment in the run. A shot whose state never arrives is REPORTED AND SKIPPED — the run
continues and the summary says what was missed, because a still of the wrong state is worse than
a missing one.

The pointer is parked off-canvas after the last click: a hover left on a chip would put one frame
in a state the others are not in.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Error as PWError
except ImportError:
    sys.exit("playwright is not installed.\n"
             "  uv pip install playwright && .venv/bin/playwright install chromium")

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "media" / "press"
W, H = 1920, 1080
SCALE = 2                     # 3840x2160 out — enough for a slide or a full-bleed page
SETTLE_MS = 900               # rows arrive on a .28s transition; let the frame stop moving
PATIENCE_MS = 150_000         # a 60s window at 8x is 7.5s of wall time, so this is many windows


# --------------------------------------------------------------------------- page state
# One expression, read repeatedly, describing everything a shot can wait for. Keeping it in a
# single place means a condition and the summary line that reports it cannot drift apart.
STATE_JS = """(blocked) => {
  const bad = new RegExp(blocked, 'i');
  const n = (s) => document.querySelectorAll(s).length;
  const rows = [...document.querySelectorAll('.boardrows .brow')];
  /* Printable AND worth printing. The first cut only screened language and landed the `you said`
     still on a row whose whole quote was the word "Get" — true, and no argument for anything. */
  const printable = rows.filter(r => {
    const q = (r.querySelector('.brow-q')?.textContent || '').trim();
    return !bad.test(q) && q.length >= 25;
  });
  return {
    clean_widest: Math.max(0, ...printable.map(r => r.querySelectorAll('.gline').length)),
    /* Real logins survive inside message text — `pseudonym()` covers the author field and not
       what people type. RISKS #53. A still is published, so the count is reported per frame
       rather than left for someone to notice later. */
    mentions: [...new Set((document.querySelector('.feed')?.textContent || '')
                 .match(/@[A-Za-z0-9_]{3,25}/g) || [])],
    chat: n('.feed > *'),
    rows: rows.length,
    board_groups: n('.boardrows .brow .gline'),
    live_groups: n('.livebox .gline'),
    widest: Math.max(0, ...rows.map(r => r.querySelectorAll('.gline').length)),
    kinds: [...new Set([...document.querySelectorAll('.brow-kind')].map(e => e.textContent))],
    split: rows.filter(r => r.getClientRects().length > 1).length,
    /* Messages seen so far, which is the only thing that separates the start of a run from its
       end: the last window of a fixture also has a full feed and no rows, and the first version
       of this script matched there and shot the `Replay finished` screen. */
    messages: +(document.getElementById('c-chat')?.textContent || '0').replace(/\\D/g, ''),
  };
}"""


def _finished(page) -> bool:
    return bool(page.evaluate(
        """() => /finished/i.test(document.getElementById('pp')?.textContent || '')"""))


def _park(page) -> None:
    page.mouse.move(2, 2)


def _shoot(page, name: str, state: dict) -> Path:
    page.wait_for_timeout(SETTLE_MS)
    dest = OUT / f"{name}.png"
    page.screenshot(path=str(dest))
    mb = dest.stat().st_size / 1e6
    print(f"    -> {dest.name}  {mb:.1f} MB  "
          f"chat={state['chat']} rows={state['rows']} groups={state['board_groups']}")
    if state["split"]:
        print(f"    ! {state['split']} board row(s) fragmented across columns in this frame")
    if state["mentions"]:
        print(f"    ! {len(state['mentions'])} real handle(s) legible in the chat column: "
              f"{' '.join(state['mentions'][:6])} — RISKS #53, blur before publishing")
    return dest


def _open(page, channel: str, speed: int = 8) -> None:
    page.goto(BASE, wait_until="load")
    page.wait_for_timeout(1200)
    page.locator(f".chip-btn:text-is('{channel}')").first.click()
    page.wait_for_timeout(600)
    page.locator(f".speeds .seg[data-speed='{speed}']").first.click()
    _park(page)


# --------------------------------------------------------------------------- the shots
# Ordered by when each state occurs in a run, so one playback yields all four in sequence: chat
# fills before the first window closes, the first window commits a row or two, and a later window
# is the one that groups hard.
SHOTS = [
    ("01_raw_chat", "the flood, before anything is grouped — dense LIVE CHAT, no committed rows",
     lambda s: s["chat"] >= 90 and s["rows"] == 0 and s["live_groups"] >= 3 and s["messages"] < 400),
    # 02 and 03 are made mutually exclusive on the group count rather than on order. Both fired
    # on the same window in the first run and produced two near-identical frames; a set where two
    # stills differ by nothing is a set of four that is really three.
    ("02_hero", "the whole dashboard, alive and lightly filled",
     lambda s: s["rows"] >= 1 and 4 <= s["board_groups"] <= 11 and s["chat"] >= 150),
    ("03_grouping", "a window the board groups hard — many counted clusters at once",
     lambda s: s["board_groups"] >= 14),
    ("04_grounded", "one grounded row, close: the trigger pills, the quote, the response",
     lambda s: s["clean_widest"] >= 4),
]


def _sweep(page, channel: str, shots, missed: list) -> list:
    """Play the channel through and take every outstanding shot the moment its state appears.

    One pass, all shots checked on every poll — not one wait per shot in order. A fixture holds a
    fixed number of 60-second windows, and the board is redrawn per window rather than
    accumulated, so waiting for shot 1's state can consume the run that shot 3's state was in.
    That is exactly what the first version did: it spent the whole replay on the opening frame and
    matched on the last window, which also has a full feed and no rows — a still of the
    `Replay finished` screen.

    A pass that ends with shots outstanding restarts playback and tries once more; two dry passes
    and the rest are reported missing rather than approximated.
    """
    taken, pending = [], list(shots)
    for attempt in (1, 2):
        if not pending:
            break
        print(f"[{channel}] pass {attempt}", flush=True)
        _open(page, channel) if attempt == 1 else _restart(page)
        while pending:
            state = page.evaluate(STATE_JS, BLOCKED)
            hit = next((s for s in pending if s[2](state)), None)
            if hit:
                name, desc, _ = hit
                print(f"  {name} — {desc}", flush=True)
                if name.endswith(("grounded", "you_said")):
                    _grounded(page)
                _park(page)
                taken.append(_shoot(page, name, state))
                pending.remove(hit)
                continue
            if _finished(page):
                break
            page.wait_for_timeout(400)
    missed.extend(name for name, _, _ in pending)
    return taken


def _restart(page) -> None:
    page.locator("#restart").click()
    page.wait_for_timeout(1500)
    _park(page)


# A press still is chosen, and choosing the streamer's most obscene sentence to headline it is a
# choice. This filters which row the camera lands on; it does NOT filter the page. The left column
# stays raw and unfiltered, because that flood is the product's whole argument and prettying it up
# would be misrepresenting what the tool is for.
BLOCKED = r"fuck|shit|bitch|cunt|nigg|retard|\bfag|whore|slut|\bcock\b|\bdick\b|pussy"

GROUNDED_JS = """(blocked) => {
  const bad = new RegExp(blocked, 'i');
  const rows = [...document.querySelectorAll('.boardrows .brow')];
  const quote = (r) => (r.querySelector('.brow-q')?.textContent || '').trim();
  const clean = rows.filter(r => !bad.test(quote(r)) && quote(r).length >= 25);
  if (!clean.length) return null;
  const best = clean.reduce((a, b) =>
    b.querySelectorAll('.gline').length > a.querySelectorAll('.gline').length ? b : a);
  best.scrollIntoView({block: 'start'});
  const pane = best.closest('.boardrows').getBoundingClientRect();
  const box = best.getBoundingClientRect();
  return {whole: box.top >= pane.top - 1 && box.bottom <= pane.bottom + 1,
          quote: (best.querySelector('.brow-q')?.textContent || '').slice(0, 60),
          dropped: rows.length - clean.length};
}"""


def _grounded(page) -> None:
    """Bring the strongest *printable* row to the top of the board pane."""
    got = page.evaluate(GROUNDED_JS, BLOCKED)
    page.wait_for_timeout(250)
    if got is None:
        print("    ! every row in this window is unprintable — framed as-is")
        return
    if got["dropped"]:
        print(f"    · skipped {got['dropped']} row(s) — unprintable or too short to carry a still")
    print(f"    · framed on: {got['quote']!r}")
    if not got["whole"]:
        print("    · the row is taller than the pane; the frame shows as much as fits")


def main() -> int:
    ap = argparse.ArgumentParser(description="Press stills of the real dashboard.")
    ap.add_argument("--list", action="store_true", help="list the shots and exit")
    ap.add_argument("--base", default=BASE, help=f"server (default {BASE})")
    ap.add_argument("--channel", default="stableronaldo", help="channel for the main set")
    ap.add_argument("--headed", action="store_true", help="show the browser while shooting")
    args = ap.parse_args()

    if args.list:
        for name, desc, _ in SHOTS:
            print(f"  {name:14} {desc}")
        print(f"  {'05_you_said':14} the `you said` pill, which needs a channel that speaks")
        return 0

    globals()["BASE"] = args.base.rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)
    done, missed = [], []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": W, "height": H},
                                  device_scale_factor=SCALE)
        page = ctx.new_page()
        try:
            print(f"[{args.channel}] {W}x{H} at {SCALE}x", flush=True)
            done += _sweep(page, args.channel, SHOTS, missed)

            # `marlon` speaks, so its rows carry `you said` where a silent channel can only ever
            # carry `on screen`. Same viewport, same context — only the channel changes.
            you_said = [("05_you_said", "a row triggered by speech, not by the screen",
                         lambda s: "you said" in s["kinds"] and s["clean_widest"] >= 2)]
            done += _sweep(page, "marlon", you_said, missed)
        except PWError as exc:
            print(f"    ! {str(exc).strip().splitlines()[0]}")
        finally:
            ctx.close()
            browser.close()

    print(f"\n{len(done)} still(s) in {OUT}")
    for name in missed:
        print(f"  missing: {name} — the state never arrived within "
              f"{PATIENCE_MS // 1000}s of playback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
