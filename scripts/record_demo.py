#!/usr/bin/env python3
"""Record the real Twinky interface as video clips — deterministically, repeatably.

Every clip here is the actual page driven by a real browser. Nothing is generated, nothing is
mocked. Re-run it after any change and the takes regenerate identically.

    # 1. serve the page (separate terminal, leave it running)
    make demo FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723

    # 2. one-time setup
    .venv/bin/pip install playwright && .venv/bin/playwright install chromium

    # 3. record
    .venv/bin/python scripts/record_demo.py                 # all shots
    .venv/bin/python scripts/record_demo.py 01 04           # only these
    .venv/bin/python scripts/record_demo.py --list

Clips land in media/clips/<name>.webm. Convert with:
    for f in media/clips/*.webm; do
      ffmpeg -y -i "$f" -c:v libx264 -crf 18 -pix_fmt yuv420p "${f%.webm}.mp4"
    done

A shot that cannot find its control is REPORTED AND SKIPPED, never faked — the run continues and
the summary at the end says what was missed.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Error as PWError
except ImportError:
    sys.exit("playwright is not installed.\n"
             "  .venv/bin/pip install playwright && .venv/bin/playwright install chromium")

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "media" / "clips"
W, H = 1920, 1080


# --------------------------------------------------------------------------- helpers
def _click_chip(page, text: str) -> bool:
    """Channel / system chips. Returns False rather than raising, so one renamed control
    costs one shot and not the whole run."""
    for sel in (f".chip-btn:text-is('{text}')", f".chip-btn:has-text('{text}')",
                f"button:text-is('{text}')"):
        try:
            node = page.locator(sel).first
            if node.count() and node.is_visible():
                node.click(timeout=3000)
                return True
        except PWError:
            continue
    print(f"    ! chip {text!r} not found — skipped")
    return False


def _set_speed(page, speed: int) -> bool:
    for sel in (f".speeds .seg[data-speed='{speed}']", f"button[data-speed='{speed}']",
                f".seg:has-text('{speed}×')"):
        try:
            node = page.locator(sel).first
            if node.count() and node.is_visible():
                node.click(timeout=3000)
                return True
        except PWError:
            continue
    print(f"    ! speed {speed}x not found — skipped")
    return False


def _scroll_over(page, target: float, seconds: float) -> None:
    """Pan to an absolute scroll position over `seconds`, stepped from Python.

    Driven off elapsed time rather than a frame or step count. The first version counted
    `requestAnimationFrame` ticks, which meant the pan took as long as headless Chromium chose to
    schedule them — a 26 s glide finished in 19 — and stepping it from Python instead cost a
    round trip per step and stretched the same pan to 83 s. Reading the clock makes the take last
    what the shot list says it lasts, whatever the frame rate underneath.
    """
    page.evaluate(
        """([target, seconds]) => new Promise(done => {
             const from = scrollY, t0 = performance.now(), ms = seconds * 1000;
             const tick = () => {
               const k = Math.min(1, (performance.now() - t0) / ms);
               scrollTo(0, from + (target - from) * k);
               if (k < 1) setTimeout(tick, 30); else done();
             };
             tick();
           })""", [target, seconds])


def _glide(page, seconds: float, to: float = 1.0) -> None:
    """Slow, even scroll — a human-looking pan for the long pages. `to` is a fraction of the
    scrollable height."""
    _scroll_over(page, page.evaluate("(to) => (document.body.scrollHeight - innerHeight) * to",
                                     to), seconds)


def _glide_to(page, selector: str, seconds: float, offset: int = 90) -> bool:
    """Pan until `selector` sits just under the header. Returns False rather than raising, so a
    renamed element costs the hold and not the shot."""
    y = page.evaluate(
        """([sel, off]) => { const el = document.querySelector(sel);
             return el ? el.getBoundingClientRect().top + scrollY - off : null; }""",
        [selector, offset])
    if y is None:
        print(f"    ! {selector} not found — panning the whole page instead")
        return False
    _scroll_over(page, max(0, y), seconds)
    return True


def _settle(page, ms: int) -> None:
    page.wait_for_timeout(ms)


# --------------------------------------------------------------------------- the shots
def shot_wordgame(page):
    """The thesis. Chat brute-forces an on-screen word with zero audio in the capture."""
    page.goto(BASE, wait_until="load")
    _settle(page, 1500)
    _click_chip(page, "stableronaldo")
    _settle(page, 800)
    _set_speed(page, 8)
    _settle(page, 62_000)          # ~8 min of stream at 8x — several word-game rounds


def shot_violet(page):
    """violet x27 — the room naming who walked on screen while he asks what's going on."""
    page.goto(BASE, wait_until="load")
    _settle(page, 1500)
    _click_chip(page, "marlon")
    _settle(page, 800)
    _set_speed(page, 8)
    _settle(page, 55_000)


def shot_questions(page):
    """The questions panel. yugi is the ONLY fixture where answered-detection visibly fires."""
    page.goto(BASE, wait_until="load")
    _settle(page, 1500)
    _click_chip(page, "yugi")
    _settle(page, 800)
    _set_speed(page, 8)
    _settle(page, 50_000)
    for label in ("Questions", "questions"):
        try:
            node = page.locator(f"button:has-text('{label}')").first
            if node.count() and node.is_visible():
                node.click(timeout=2000)
                break
        except PWError:
            continue
    _settle(page, 12_000)


def shot_agent_vs_baseline(page):
    """The same window, both systems. The comparison the eval measures, shown."""
    page.goto(BASE, wait_until="load")
    _settle(page, 1500)
    _click_chip(page, "marlon")
    _settle(page, 800)
    _set_speed(page, 8)
    _settle(page, 26_000)
    _click_chip(page, "baseline")
    _settle(page, 26_000)
    _click_chip(page, "agent")
    _settle(page, 8_000)


def shot_method(page):
    """The method page — the agent graph and the gate codes.

    The graph is what this shot is for, so it is panned to and held on rather than passed over
    in a single sweep of a page that is many screens long."""
    page.goto(f"{BASE}/method", wait_until="load")
    _settle(page, 5000)                # let the hero panel play its sequence out
    _glide_to(page, "figure.graph", 7)
    _settle(page, 9000)                # the hold: read the tool counts and the gate codes
    _glide(page, 12, to=1.0)
    _settle(page, 2000)


def shot_replay_live(page):
    """The REPLAY | LIVE control. Does not go live — no spend, no network claim."""
    page.goto(BASE, wait_until="load")
    _settle(page, 2500)
    for label in ("Live", "LIVE"):
        try:
            node = page.locator(f"button:has-text('{label}'), .seg:has-text('{label}')").first
            if node.count() and node.is_visible():
                node.click(timeout=2000)
                break
        except PWError:
            continue
    _settle(page, 6000)
    for label in ("Replay", "REPLAY"):
        try:
            node = page.locator(f"button:has-text('{label}'), .seg:has-text('{label}')").first
            if node.count() and node.is_visible():
                node.click(timeout=2000)
                break
        except PWError:
            continue
    _settle(page, 5000)


SHOTS = {
    "01": ("01_wordgame_board", shot_wordgame,
           "stableronaldo 8x — the board names the on-screen word game"),
    "02": ("02_violet_27", shot_violet,
           "marlon 8x — violet x27 under the streamer's own quote"),
    "03": ("03_questions_panel", shot_questions,
           "yugi 8x — the questions panel, the only fixture where answers fire"),
    "04": ("04_agent_vs_baseline", shot_agent_vs_baseline,
           "same window, agent then baseline then back"),
    "05": ("05_method_graph", shot_method,
           "the method page: agent graph, gate codes, measured table"),
    "06": ("06_replay_live_tabs", shot_replay_live,
           "the REPLAY | LIVE control (does not go live, spends nothing)"),
}


# --------------------------------------------------------------------------- runner
def main() -> int:
    ap = argparse.ArgumentParser(description="Record the real interface as video clips.")
    ap.add_argument("ids", nargs="*", help="shot ids to record (default: all)")
    ap.add_argument("--list", action="store_true", help="list the shots and exit")
    ap.add_argument("--base", default=BASE, help=f"server (default {BASE})")
    ap.add_argument("--headed", action="store_true", help="show the browser while recording")
    args = ap.parse_args()

    if args.list:
        for sid, (name, _, desc) in SHOTS.items():
            print(f"  {sid}  {name:26} {desc}")
        return 0

    globals()["BASE"] = args.base.rstrip("/")
    chosen = args.ids or list(SHOTS)
    unknown = [c for c in chosen if c not in SHOTS]
    if unknown:
        return print(f"unknown shot id(s): {', '.join(unknown)}  (try --list)") or 2

    OUT.mkdir(parents=True, exist_ok=True)
    done, failed = [], []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        try:
            for sid in chosen:
                name, fn, desc = SHOTS[sid]
                print(f"[{sid}] {name} — {desc}")
                ctx = browser.new_context(
                    viewport={"width": W, "height": H},
                    device_scale_factor=1,
                    record_video_dir=str(OUT),
                    record_video_size={"width": W, "height": H},
                )
                page = ctx.new_page()
                started = time.time()
                try:
                    fn(page)
                except PWError as exc:
                    first = str(exc).strip().splitlines()[0]
                    print(f"    ! {first}")
                    failed.append((name, first))
                raw = page.video.path() if page.video else None
                ctx.close()                     # the file is only finalised on close
                if raw:
                    dest = OUT / f"{name}.webm"
                    if dest.exists():
                        dest.unlink()
                    shutil.move(raw, dest)
                    mb = dest.stat().st_size / 1e6
                    print(f"    -> {dest.relative_to(OUT.parents[1])}  "
                          f"{time.time() - started:.0f}s  {mb:.1f} MB")
                    done.append(dest)
        finally:
            browser.close()

    print(f"\n{len(done)} clip(s) in {OUT}")
    for name, why in failed:
        print(f"  incomplete: {name} — {why}")
    if failed:
        print("\nA clip listed above still recorded whatever the page did show. Watch it before "
              "re-running: a renamed control is a one-line fix in this script, not a rebuild.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
