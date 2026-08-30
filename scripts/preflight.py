"""Pre-submission check. One command that says whether this is ready to hand in.

Written at T-15h, after discovering that `origin/main` was thirty-one commits behind local while
`RISKS.md` said the only remaining repository action was "make it public". Making it public in
that state would have published a project called Twitch Agent, with a two-column dashboard, none
of the grouping work, and none of the three measured experiments — while every document described
something else.

Nothing here fixes anything. It reports, loudly, in the order that matters, and exits non-zero if
a hard blocker is unresolved. Network checks degrade to UNKNOWN rather than failing, because a
check that lies when offline is worse than one that admits it.

    make preflight
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OK, FAIL, TODO, UNKNOWN = "PASS", "FAIL", "TODO", "????"


def run(*args, **kw):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=60, **kw)


def check_uncommitted():
    """Uncommitted SOURCE is a blocker. A capture left on disk is not.

    Three partial captures appeared mid-session — `meta.json` and a gitignored `raw/`, no derived
    events. Blocking a submission on those would be a false alarm at three in the morning, and a
    checklist that cries wolf once stops being read.
    """
    lines = [l for l in run("git", "status", "--porcelain").stdout.splitlines() if l.strip()]
    captures = [l for l in lines if l.startswith("??") and "/fixtures/" in l]
    real = [l for l in lines if l not in captures]

    note = f"; {len(captures)} untracked capture(s) on disk, correctly not committed" \
        if captures else ""
    if real:
        return FAIL, f"{len(real)} uncommitted change(s){note}"
    return OK, f"no uncommitted source{note}"


def check_pushed():
    """The one that started this. A public repository showing old work is worse than a private
    one, because it looks finished."""
    if run("git", "fetch", "origin").returncode != 0:
        return UNKNOWN, "cannot reach origin — check manually before making the repo public"
    ahead = run("git", "rev-list", "--count", "origin/main..HEAD").stdout.strip()
    behind = run("git", "rev-list", "--count", "HEAD..origin/main").stdout.strip()
    if ahead == "0" and behind == "0":
        return OK, "origin/main matches local"
    return FAIL, (f"local is {ahead} commit(s) ahead of origin/main"
                  f"{f', {behind} behind' if behind != '0' else ''} — PUSH BEFORE PUBLISHING")


def check_tests():
    done = run(sys.executable, "-m", "pytest", "-q", "tests")
    match = re.search(r"(\d+) passed", done.stdout)
    if done.returncode == 0 and match:
        return OK, f"{match.group(1)} passed"
    return FAIL, "make test is not green"


def check_eval():
    done = run(sys.executable, "-m", "evals.run_eval", "--ablation", "--out", "/tmp/preflight",
               env={"TS_LLM_MODE": "replay", "PATH": "/usr/bin:/bin", "HOME": "/tmp"})
    match = re.search(r"'hits': (\d+), 'misses': (\d+)", done.stdout)
    if not match:
        return FAIL, "make eval did not report cache counts"
    hits, misses = match.groups()
    if misses != "0":
        return FAIL, f"{misses} cache miss(es) — keyless reproduction is broken"
    return OK, f"{hits} hits, 0 misses, no keys"


def check_secrets():
    done = run(sys.executable, "scripts/scan_secrets.py")
    return (OK, "no secret can reach the archive") if done.returncode == 0 else (
        FAIL, "scan_secrets found something shippable")


def check_gold():
    files = sorted((REPO / "evals/gold").glob("*.json"))
    confirmed = sum(json.loads(f.read_text(encoding="utf-8")).get("reviewed") is True
                    for f in files)
    if confirmed == len(files):
        return OK, f"all {len(files)} labels human-confirmed"
    return TODO, (f"{confirmed}/{len(files)} confirmed — run `make review`. Unconfirmed is "
                  f"ALLOWED and is stated in README §6; it is not a blocker, only a cost")


def check_video():
    found = [p for p in (REPO / "video").iterdir()
             if p.suffix.lower() in {".mp4", ".mov", ".webm", ".m4v"}] \
        if (REPO / "video").is_dir() else []
    return (OK, found[0].name) if found else (FAIL, "no video file — a missing deliverable scores nothing")


def check_visibility():
    done = run("gh", "repo", "view", "tolyaho/twinky", "--json", "visibility")
    if done.returncode != 0:
        return UNKNOWN, "gh unavailable — confirm the repository is public by hand"
    visibility = json.loads(done.stdout).get("visibility", "").lower()
    return (OK, "public") if visibility == "public" else (FAIL, f"repository is {visibility}")


CHECKS = [
    ("video recorded", check_video, True),
    ("pushed to origin", check_pushed, True),
    ("repository public", check_visibility, True),
    ("no secret ships", check_secrets, True),
    ("tests green", check_tests, True),
    ("eval reproduces keyless", check_eval, True),
    ("working tree committed", check_uncommitted, True),
    ("gold labels reviewed", check_gold, False),
]


def main() -> int:
    print("Pre-submission check\n")
    blocked = []
    for name, fn, hard in CHECKS:
        try:
            state, detail = fn()
        except Exception as exc:                     # noqa: BLE001 - never crash the checklist
            state, detail = UNKNOWN, f"{type(exc).__name__}: {exc}"
        print(f"  [{state}] {name:26s} {detail}")
        if hard and state in (FAIL,):
            blocked.append(name)

    print()
    if blocked:
        print(f"NOT READY — {len(blocked)} blocker(s): {', '.join(blocked)}")
        return 1
    print("Every hard check passed. Anything marked TODO is a stated cost, not a blocker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
