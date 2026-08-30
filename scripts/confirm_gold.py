"""Flip a gold label from model-drafted to human-confirmed, one case at a time.

`evals/REVIEW_ME.md` says the review takes ten minutes and needs no JSON. Then it asks you to
hand-edit `"reviewed": true` across eleven files, which is the part that goes wrong at three in
the morning — a stray comma, the wrong case, or a quiet edit to something that is not the flag.

This does exactly one thing: set `reviewed` to `true` on the cases you name, and record who said
so and when. It touches no other field, and it refuses a case id that does not exist rather than
creating one.

    python scripts/confirm_gold.py --list
    python scripts/confirm_gold.py --confirm c05_warning_no_cause --by "your name"
    python scripts/confirm_gold.py --disagree c11_sarcasm_mockery --note "cause is the clip at 4:12"

**There is deliberately no `--all`.** Confirming eleven labels with one keystroke is how a review
becomes a rubber stamp, and the flag exists precisely to distinguish a review that happened from
one that was asserted. Name them individually or leave them false — an unreviewed label that says
so is worth more than a confirmed one that is not true.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

GOLD = Path(__file__).resolve().parents[1] / "evals/gold"


def cases() -> List[Path]:
    return sorted(GOLD.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, doc: dict) -> None:
    # Trailing newline and two-space indent, matching what is committed, so `git diff` shows the
    # one line that changed rather than the whole file.
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def show() -> int:
    confirmed = 0
    for path in cases():
        doc = _load(path)
        state = doc.get("reviewed")
        mark = "confirmed" if state is True else ("DISAGREED" if state == "disagreed" else "—")
        by = doc.get("reviewed_by")
        print(f"  {'✔' if state is True else ' '} {path.stem:32s} {mark:10s} "
              f"{by or ''}")
        confirmed += state is True
    total = len(cases())
    print(f"\n{confirmed} of {total} confirmed by a person. "
          f"{total - confirmed} still model-drafted, and README §6 says so.")
    return 0


def apply(names: List[str], *, value, by: str, note: str | None) -> int:
    by_stem = {p.stem: p for p in cases()}
    unknown = [n for n in names if n not in by_stem]
    if unknown:
        print(f"no such case: {', '.join(unknown)}", file=sys.stderr)
        print(f"known: {', '.join(sorted(by_stem))}", file=sys.stderr)
        return 2

    for name in names:
        path = by_stem[name]
        doc = _load(path)
        doc["reviewed"] = value
        doc["reviewed_by"] = by
        if note:
            doc["review_note"] = note
        _write(path, doc)
        print(f"  {name}: reviewed = {value!r}, by {by!r}")
    print("\nCommit this. The flag is only meaningful because the change is visible in git.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show the review state of every case")
    ap.add_argument("--confirm", nargs="+", metavar="CASE",
                    help="mark these cases reviewed and correct")
    ap.add_argument("--disagree", nargs="+", metavar="CASE",
                    help="mark these cases reviewed and WRONG; use --note to say what is right")
    ap.add_argument("--by", default="", help="who is confirming — required to confirm")
    ap.add_argument("--note", help="what the right answer is, when disagreeing")
    args = ap.parse_args(argv)

    if args.list or not (args.confirm or args.disagree):
        return show()
    if not args.by.strip():
        print("--by is required: an anonymous confirmation is not a confirmation.",
              file=sys.stderr)
        return 2
    if args.confirm:
        return apply(args.confirm, value=True, by=args.by, note=args.note)
    return apply(args.disagree, value="disagreed", by=args.by, note=args.note)


if __name__ == "__main__":
    raise SystemExit(main())
