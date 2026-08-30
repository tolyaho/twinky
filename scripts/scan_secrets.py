"""Secret scan, run by `make scan` before archiving.

Written as a script rather than a grep line in the Makefile for three reasons, each of which was
a real defect in the grep version:

  1. `grep -r .` on macOS never reached `.env`, the one file in this tree holding live
     credentials. The scan reported on everything except the thing that mattered.
  2. The pattern list lived in the Makefile, so the Makefile matched its own patterns and the
     scan failed permanently. A check that is always red is a check nobody reads.
  3. `legacy/` was excluded from the scan while still being present in the tree, so a credential
     committed there was invisible to the gate and would ship in the archive.

It prints `path:line` and the name of the rule that fired. It never prints the matched text.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

REPO = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
             "node_modules", ".ruff_cache", "dist", "build", ".idea"}

# Files that exist locally on purpose and must never leave the machine. Finding a secret in one
# of these is expected; shipping the file is the failure.
LOCAL_ONLY = {".env", ".capture_salt"}

# A file whose whole job is to show the shape of a secret without being one.
ALLOWLIST = {".env.example", "scan_secrets.py",
             # exists to test the scanner, so it necessarily contains decoy keys
             "test_scan_secrets.py"}

BINARY_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".wav", ".opus", ".ogg", ".mp3",
                   ".mp4", ".zip", ".gz", ".pdf", ".ico", ".woff", ".woff2", ".so", ".dylib"}

# Rule names are what gets printed. Keep them descriptive: the operator sees the name, not the
# match.
RULES: List[Tuple[str, re.Pattern]] = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("twitch-oauth", re.compile(r"oauth:[A-Za-z0-9]{10,}")),
    ("aws-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # A database user and host sitting next to a password are part of the same credential, so
    # they are treated as one: `legacy/README.original.md` holds the whole connection block and
    # only the password line fired on the first pass.
    ("assigned-credential", re.compile(
        r"\b[A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|OAUTH|SECRET|PASSWORD|CLIENT_ID"
        r"|DB_USER|DB_HOST|DB_NAME)"
        r"\s*[=:]\s*[\"']?[^\s\"'<${}#]{8,}")),
]


def candidate_files(root: Path) -> Iterator[Path]:
    """Every text file under root, dotfiles included. `os.walk` is used rather than a glob so
    that hidden files are never silently skipped — which is exactly how the previous scan
    missed `.env`."""
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in sorted(current.iterdir()):
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            elif entry.suffix.lower() not in BINARY_SUFFIXES:
                yield entry


# A documentation example is not a credential. `legacy/README.original.md` is six lines of
# `DB_PASSWORD=your_password` inside a "Create `.env`:" block, and it outranked the eight real
# credentials in `.env` as the project's top finding for a full day (RISKS #16, withdrawn; #35).
# A scanner that cries wolf on its own README gets switched off, which is the failure mode the
# #18 rewrite already cost this project once.
PLACEHOLDER = re.compile(
    r"=\s*[\"']?\s*(?:"
    r"your[-_ ]?\w{0,16}"                       # your_password, your-key, YOUR_TOKEN
    r"|my[-_ ]?(?:key|token|password|secret)\w{0,10}"
    r"|(?:replace|change)[-_ ]?(?:me|this|with)\w*"
    r"|placeholder\w*|dummy\w*|example\w*|sample\w*|redacted\w*|elided\w*"
    r"|x{3,}|\.{3,}|\*{3,}"
    r"|<[^>]*>"
    r"|localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal|example\.(?:com|org)"
    r")\s*[\"']?\s*(?=[\s`,.;)\]}]|$)",
    re.IGNORECASE)


def is_placeholder(line: str) -> bool:
    """True when the assigned value is obviously a stand-in rather than a secret.

    The whole line is checked, comments included. An earlier version stripped everything after
    the first `#` before matching, which emptied any line that *began* with one — so a comment
    explaining the placeholder rule was itself reported as a leaked credential.
    """
    return bool(PLACEHOLDER.search(line.rstrip()))


def scan_file(path: Path) -> List[Tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if is_placeholder(line):
            continue
        for name, pattern in RULES:
            if pattern.search(line):
                hits.append((lineno, name))
                break
    return hits


def is_git_ignored(path: Path, root: Path) -> bool:
    """Is this file excluded from the repository by `.gitignore`?

    `make archive` builds from `git archive HEAD`, so a tracked-and-ignored file cannot enter the
    zip by construction. A local `.env` is therefore expected and correct, and failing the whole
    scan for it teaches the author that `make scan` always fails — which is how a security check
    stops being read. In the extracted archive there is no git at all, and then any local-only
    file present IS a real failure, which is exactly what the `False` return produces.
    """
    import subprocess

    try:
        done = subprocess.run(["git", "check-ignore", "-q", str(path)],
                              cwd=root, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


SKIP_IN_HISTORY = ("cache/", "evals/fixtures/", "trajectories/", "evidence/raw-results/")


def scan_history() -> List[str]:
    """Every version of every text file ever committed, not just the current ones.

    Making a repository public exposes its whole history. A credential that was committed once
    and removed in the next commit is still there, and `git log --name-only` will not find it
    because the leak is in the CONTENT, not the filename. Uses `cat-file --batch` — one process
    for the whole history rather than one per object.
    """
    import subprocess

    listing = subprocess.run(["git", "rev-list", "--objects", "--all"],
                             capture_output=True, text=True, timeout=120)
    named = []
    for line in listing.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and not parts[1].startswith(SKIP_IN_HISTORY):
            named.append(parts)
    if not named:
        return []

    batch = subprocess.run(["git", "cat-file", "--batch"],
                           input="\n".join(sha for sha, _ in named).encode(),
                           capture_output=True, timeout=300)
    out, findings, pos = batch.stdout, [], 0
    for sha, path in named:
        header_end = out.find(b"\n", pos)
        if header_end == -1:
            break
        header = out[pos:header_end].split()
        if len(header) < 3:
            pos = header_end + 1
            continue
        size = int(header[2])
        body, pos = out[header_end + 1:header_end + 1 + size], header_end + 2 + size
        if b"\0" in body[:1024] or Path(path).name in ALLOWLIST:
            continue
        text = body.decode("utf-8", "replace")
        lines = text.splitlines()
        for name, rule in RULES:
            for m in rule.finditer(text):
                lineno = text[:m.start()].count("\n")
                if lineno < len(lines) and PLACEHOLDER.search(lines[lineno]):
                    continue
                findings.append(f"{path}@{sha[:8]}:{lineno + 1}  [{name}]")
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=REPO)
    ap.add_argument("--history", action="store_true",
                    help="scan every version of every file ever committed. Making a repository "
                         "public exposes all of it, and a filename check cannot see a key that "
                         "was pasted into a doc and removed the next commit.")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if args.history:
        findings = scan_history()
        if findings:
            print("SECRET IN GIT HISTORY — publishing this repository would expose it:",
                  file=sys.stderr)
            for line in findings:
                print(f"  {line}", file=sys.stderr)
            return 1
        print("history clean — no credential pattern in any committed version of any file")
        return 0

    blockers: List[str] = []
    leaks: List[str] = []
    excluded: List[str] = []

    for path in candidate_files(root):
        if path.name in ALLOWLIST:
            continue
        rel = path.relative_to(root)
        hits = [f"{rel}:{lineno}  [{rule}]" for lineno, rule in scan_file(path)]
        if not hits:
            continue
        if path.name not in LOCAL_ONLY:
            leaks.extend(hits)
        elif is_git_ignored(path, root):
            excluded.append(str(rel))          # expected, and provably cannot reach the archive
        else:
            blockers.extend(hits)

    if leaks:
        print("SECRET IN A PROJECT FILE — do not archive, rotate the credential:", file=sys.stderr)
        for line in leaks:
            print(f"  {line}", file=sys.stderr)
    if blockers:
        print("LOCAL-ONLY FILE WITH CREDENTIALS — expected to exist, must not ship:",
              file=sys.stderr)
        for line in blockers:
            print(f"  {line}", file=sys.stderr)
        print("  Exclude these from the archive. `.gitignore` does not protect a directory that "
              "is zipped rather than committed.", file=sys.stderr)

    if leaks or blockers:
        return 1
    if excluded:
        # Reported, never silent: the author should see that the scanner found them and knows
        # why they are allowed. Silence here would be indistinguishable from not looking.
        print(f"local-only and git-ignored, so they cannot reach the archive: "
              f"{', '.join(sorted(set(excluded)))}")
    print("clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
