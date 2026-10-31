#!/usr/bin/env python3
"""Bundle a slice of a real committed fixture as the labelled REPLAY example.

Reads a busy, already-pseudonymised capture from `evals/fixtures/` and writes the first N rows to
`web/src/data/replay.json` as {id, ts_ms, login, text}. The replay source re-stamps timestamps
onto the live clock at play time, so only the relative spacing here matters. Nothing is modified
in the source fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
OUT = HERE.parents[1] / "src" / "data" / "replay.json"
N = 700

CANDIDATES = [
    REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl",
    REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/raw/chat.jsonl",
]


def main() -> None:
    path = next((p for p in CANDIDATES if p.exists()), None)
    if path is None:
        raise SystemExit("no fixture found")
    rows = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= N:
                break
            r = json.loads(line)
            rows.append({
                "id": f"rp{i:04d}",
                "ts_ms": int(r["ts_ms"]),
                "login": r["author"],   # already pseudonymised in the committed fixture
                "text": r["text"],
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    span = (rows[-1]["ts_ms"] - rows[0]["ts_ms"]) / 1000 if rows else 0
    print(f"wrote {OUT} — {len(rows)} rows from {path.name}, spanning {span:.0f}s")


if __name__ == "__main__":
    main()
