"""Command line entry point.

    python -m ts.cli replay   --fixture evals/fixtures/sample
    python -m ts.cli baseline --fixture evals/fixtures/sample [--chat-only]
    python -m ts.cli capture  --channel NAME --minutes 10 --out evals/fixtures   # no keys
    python -m ts.cli enrich   --fixture evals/fixtures/NAME                     # needs keys
    python -m ts.cli debrief  --fixture evals/fixtures/sample   # post-stream document
    python -m ts.cli serve    --fixture evals/fixtures/sample --port 8000
    python -m ts.cli inspect  --fixture evals/fixtures/sample
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .cache import CacheMiss, ResponseCache
from .ingest.replay import load_fixture, load_meta
from .workflow.reduce import compression_ratio, reduce_chat

# Analysis windows are bounded by TIME, not by event count: a busy minute and a quiet minute
# must produce the same window boundaries, or two runs of the same fixture disagree.
WINDOW_MS = 60_000


def windows(start_ms: int, end_ms: int, size_ms: int = WINDOW_MS) -> List[Tuple[int, int]]:
    """Tile a fixture span into analysis windows.

    Derived from fixture content only - never from wall-clock time, arrival order or event
    volume. The window bounds go into the prompt, so a non-deterministic tiling would change
    every cache key and `make replay` would stop reproducing published numbers.
    """
    if size_ms <= 0:
        raise ValueError("window size must be positive")
    out: List[Tuple[int, int]] = []
    t = start_ms
    while t < end_ms:
        out.append((t, min(t + size_ms, end_ms)))
        t += size_ms
    return out or [(start_ms, start_ms + size_ms)]


def cmd_inspect(args: argparse.Namespace) -> int:
    """Works today. Sanity-checks a fixture without any model call."""
    index = load_fixture(args.fixture)
    meta = load_meta(args.fixture)
    chat = [e for e in index if e.type == "chat_message"]
    bursts = reduce_chat(chat)
    print(json.dumps({
        "fixture": str(args.fixture),
        "meta": meta,
        "events": len(index),
        "chat": len(chat),
        "transcript": sum(1 for e in index if e.type == "transcript_segment"),
        "frames": sum(1 for e in index if e.type == "frame_caption"),
        "span_ms": [index.start_ms, index.end_ms],
        "bursts_after_reduction": len(bursts),
        "compression_ratio": round(compression_ratio(index.events, bursts), 3),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    """Raw capture. No API keys. Do this while the stream is live."""
    import asyncio
    import logging

    from .ingest.capture import capture

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = asyncio.run(capture(args.channel, args.minutes, args.out))
    print(f"captured -> {root}\nnext: make enrich FIXTURE={root}")
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    from .ingest.enrich import enrich

    root = enrich(args.fixture, ResponseCache())
    print(f"enriched -> {root}\nnext: python -m ts.cli inspect --fixture {root}")
    return 0


# --------------------------------------------------------------------------- run over a fixture
Runner = Callable[[str, int, int], Dict[str, Any]]
MakeRunner = Callable[[Any, ResponseCache], Runner]


def _run_over_fixture(args: argparse.Namespace, system: str, make_runner: MakeRunner) -> int:
    """One tiled pass over a fixture, written to `--out` as a single JSON document.

    Both systems go through this function on identical windows. That is a fairness requirement,
    not a convenience: the eval compares them, so anything that differs between the two paths
    other than the system itself would show up as a measured improvement it did not earn.
    """
    index = load_fixture(args.fixture)
    meta = load_meta(args.fixture)
    fixture_id = meta.get("fixture_id") or Path(args.fixture).name
    cache = ResponseCache()
    runner = make_runner(index, cache)

    results: List[Dict[str, Any]] = []
    try:
        for i, (start_ms, end_ms) in enumerate(windows(index.start_ms, index.end_ms + 1)):
            case_id = f"{fixture_id}_w{i:02d}"
            results.append({"case_id": case_id, "window_ms": [start_ms, end_ms],
                            **runner(case_id, start_ms, end_ms)})
    except CacheMiss as exc:
        print(f"{exc}\n\nNothing is recorded for this fixture yet. Record it once with "
              f"TS_LLM_MODE=record, then re-run this command unchanged.", file=sys.stderr)
        return 3

    # Counts, not rates. `evals/scorer.py` owns every published metric; a second implementation
    # here would eventually disagree with it, and the disagreement would surface in the report.
    doc = {
        "system": system,
        "fixture": str(args.fixture),
        "fixture_id": fixture_id,
        "mode": cache.mode,
        "window_size_ms": WINDOW_MS,
        "span_ms": [index.start_ms, index.end_ms],
        "counts": {
            "windows": len(results),
            "verified": sum(len(r["verified"]) for r in results),
            "rejected": sum(len(r["rejected"]) for r in results),
        },
        "cache": cache.stats(),
        "windows": results,
    }

    out_path = Path(args.out) / f"{fixture_id}.{system}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({k: doc[k] for k in ("system", "fixture_id", "mode", "counts", "cache")},
                     ensure_ascii=False))
    print(f"wrote -> {out_path}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    from .workflow.agent import AudienceSignalAgent

    def make_runner(index, cache):
        agent = AudienceSignalAgent(index, cache)
        return lambda case_id, start_ms, end_ms: agent.run(case_id, start_ms, end_ms)

    return _run_over_fixture(args, "agent", make_runner)


def cmd_baseline(args: argparse.Namespace) -> int:
    from .baseline import single_prompt

    system = "ablation_chat_only" if args.chat_only else "baseline"

    def make_runner(index, cache):
        return lambda case_id, start_ms, end_ms: single_prompt.run(
            index, cache, case_id, start_ms, end_ms, chat_only=args.chat_only)

    return _run_over_fixture(args, system, make_runner)


def cmd_debrief(args: argparse.Namespace) -> int:
    """Roll a completed replay up into the post-stream document. No model call: it reorganises
    what `make replay` already verified."""
    from .report.debrief import build, render_markdown

    index = load_fixture(args.fixture)
    meta = load_meta(args.fixture)
    fixture_id = meta.get("fixture_id") or Path(args.fixture).name

    result_path = Path(args.out) / f"{fixture_id}.agent.json"
    if not result_path.exists():
        print(f"{result_path} not found. Run `make replay FIXTURE={args.fixture}` first — the "
              "debrief reports verified cards, it does not produce them.", file=sys.stderr)
        return 4

    result = json.loads(result_path.read_text(encoding="utf-8"))
    cards = [c for w in result["windows"] for c in w["verified"]]

    document = build(cards, meta, index)
    md_path = Path(args.out) / f"{fixture_id}.debrief.md"
    md_path.write_text(render_markdown(document), encoding="utf-8")
    (Path(args.out) / f"{fixture_id}.debrief.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({"verified_cards": document["verified_cards"],
                      "sections": {k: len(v) for k, v in document["sections"].items()}},
                     ensure_ascii=False))
    print(f"wrote -> {md_path}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .report.serve import serve

    return serve(args.fixture, args.out, args.port)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ts")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, func in (("replay", cmd_replay), ("baseline", cmd_baseline)):
        sp = sub.add_parser(name)
        sp.add_argument("--fixture", required=True, type=Path)
        sp.add_argument("--out", type=Path, default=Path("evidence/raw-results"))
        if name == "baseline":
            sp.add_argument("--chat-only", action="store_true")
        sp.set_defaults(func=func)

    sp = sub.add_parser("inspect")
    sp.add_argument("--fixture", required=True, type=Path)
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("capture")
    sp.add_argument("--channel", required=True)
    sp.add_argument("--minutes", type=int, default=10)
    sp.add_argument("--out", type=Path, default=Path("evals/fixtures"))
    sp.set_defaults(func=cmd_capture)

    sp = sub.add_parser("enrich")
    sp.add_argument("--fixture", required=True, type=Path)
    sp.set_defaults(func=cmd_enrich)

    sp = sub.add_parser("debrief")
    sp.add_argument("--fixture", required=True, type=Path)
    sp.add_argument("--out", type=Path, default=Path("evidence/raw-results"))
    sp.set_defaults(func=cmd_debrief)

    sp = sub.add_parser("serve")
    sp.add_argument("--fixture", required=True, type=Path)
    sp.add_argument("--out", type=Path, default=Path("evidence/raw-results"))
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
