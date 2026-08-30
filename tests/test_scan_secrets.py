"""The secret scan is part of the qualification gate, so it has to be trustworthy itself.

Two of these are regression tests for defects the previous grep-based scan actually had: it
never reached `.env` at all, and it matched its own pattern list and so failed permanently.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scan_secrets  # noqa: E402

SECRET = "sk-ant-api03-NOTAREALKEYbutlongenoughtomatch"


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "clean.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def run(tree, capsys):
    code = scan_secrets.main(["--root", str(tree)])
    return code, capsys.readouterr()


def test_a_clean_tree_passes(tree, capsys):
    code, out = run(tree, capsys)

    assert code == 0
    assert "clean" in out.out


def test_a_key_in_a_source_file_is_a_leak(tree, capsys):
    (tree / "src" / "leaky.py").write_text(f'KEY = "{SECRET}"\n', encoding="utf-8")

    code, out = run(tree, capsys)

    assert code == 1
    assert "SECRET IN A PROJECT FILE" in out.err
    assert "src/leaky.py:1" in out.err


def test_a_dotfile_is_scanned(tree, capsys):
    """The regression that matters: `grep -r .` on macOS never reached `.env`, so the scan
    reported on everything except the one file holding live credentials."""
    (tree / ".env").write_text(f"ANTHROPIC_API_KEY={SECRET}\n", encoding="utf-8")

    code, out = run(tree, capsys)

    assert code == 1
    assert ".env:1" in out.err


def test_env_is_a_shipping_blocker_not_a_leak(tree, capsys):
    """`.env` is supposed to exist on the machine. Shipping it is the failure, not holding it."""
    (tree / ".env").write_text(f"ANTHROPIC_API_KEY={SECRET}\n", encoding="utf-8")

    _, out = run(tree, capsys)

    assert "LOCAL-ONLY FILE WITH CREDENTIALS" in out.err
    assert "SECRET IN A PROJECT FILE" not in out.err


def test_the_scan_never_prints_the_secret(tree, capsys):
    (tree / "src" / "leaky.py").write_text(f'KEY = "{SECRET}"\n', encoding="utf-8")

    _, out = run(tree, capsys)

    assert SECRET not in out.err and SECRET not in out.out
    assert "[anthropic-key]" in out.err   # the rule name, not the match


def test_the_example_file_is_allowed_to_look_like_a_secret(tree, capsys):
    (tree / ".env.example").write_text("ANTHROPIC_API_KEY=sk-ant-replace-me-with-your-key\n",
                                       encoding="utf-8")

    assert run(tree, capsys)[0] == 0


def test_a_placeholder_assignment_is_not_a_credential(tree, capsys):
    (tree / ".env.local").write_text("DB_PASSWORD=\nAPI_KEY=<your key here>\n", encoding="utf-8")

    assert run(tree, capsys)[0] == 0


def test_virtualenvs_and_binaries_are_skipped(tree, capsys):
    (tree / ".venv").mkdir()
    (tree / ".venv" / "creds.py").write_text(f'K="{SECRET}"\n', encoding="utf-8")
    (tree / "frame.jpg").write_text(SECRET, encoding="utf-8")

    assert run(tree, capsys)[0] == 0


def test_the_scanner_does_not_match_its_own_pattern_list():
    """The grep version lived in the Makefile, matched itself, and so was red on every run — a
    check that always fails is a check nobody reads."""
    assert scan_secrets.scan_file(Path(scan_secrets.__file__)) == []
    assert "scan_secrets.py" in scan_secrets.ALLOWLIST


def test_the_real_tree_is_scanned_including_legacy():
    """`legacy/` was excluded by the old scan while still sitting in the tree, so a credential
    committed there was invisible to the gate."""
    repo = Path(scan_secrets.REPO)
    scanned = {p.relative_to(repo).parts[0] for p in scan_secrets.candidate_files(repo)}

    assert "legacy" in scanned
    assert ".venv" not in scanned


# --------------------------------------------------------------- placeholders (RISKS #35)
@pytest.mark.parametrize("line", [
    "DB_PASSWORD=your_password",
    "DEEPGRAM_API_KEY=your_key",
    "TWITCH_OAUTH=your_token",
    'API_KEY="YOUR_KEY_HERE"',
    "SECRET=changeme",
    "CLIENT_ID=replace-me",
    "DB_HOST=localhost",
    "DB_HOST=127.0.0.1",
    "PASSWORD=xxxxxx",
    "ACCESS_TOKEN=<your token>",
    "the row says `DB_PASSWORD=your_password`, which is a placeholder",
])
def test_a_documentation_placeholder_is_not_a_credential(line):
    """`legacy/README.original.md` is six lines of `DB_PASSWORD=your_password` inside a
    'Create .env:' block. It outranked the eight real credentials in `.env` as the project's
    top finding for a full day (RISKS #16, withdrawn). A scanner that cries wolf on its own
    README gets switched off — which is exactly what the #18 rewrite already cost once."""
    assert scan_secrets.is_placeholder(line), line


@pytest.mark.parametrize("line", [
    "DB_PASSWORD=hunter2correcthorse",
    "DEEPGRAM_API_KEY=8f3c1a9b2d7e4f6a0c5b8e1d",
    "SECRET=yourself_is_not_a_placeholder_prefix_9182",
])
def test_a_real_looking_value_is_still_reported(line):
    """The placeholder rule must not become a hole: anything that is not obviously a stand-in
    still fires."""
    assert not scan_secrets.is_placeholder(line), line


def test_the_project_tree_has_no_committed_secret():
    """The gate condition itself, run against this repository rather than a fixture."""
    from pathlib import Path

    root = Path(scan_secrets.__file__).resolve().parents[1]
    leaks = []
    for path in scan_secrets.candidate_files(root):
        if path.name in scan_secrets.ALLOWLIST or path.name in scan_secrets.LOCAL_ONLY:
            continue
        for lineno, rule in scan_secrets.scan_file(path):
            leaks.append(f"{path.relative_to(root)}:{lineno} [{rule}]")

    assert not leaks, f"committed secrets: {leaks}"


# --------------------------------------------------------------- packaging (RISKS #13, #17)
def _shipped(root):
    """What would reach a judge: the tracked set in a checkout, the files on disk in an unpacked
    archive. `git ls-files` raises outside a repository, and these tests run in BOTH — the gate
    caught exactly that, with two failures inside the extracted zip."""
    import subprocess

    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True, check=True).stdout.split()
        return out, "checkout"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ([str(p.relative_to(root)) for p in root.rglob("*")
                 if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts],
                "archive")


def test_no_credential_file_is_tracked_by_git():
    """`.gitignore` does not protect a zip — but `make archive` builds from `git archive HEAD`,
    so an untracked file cannot enter the archive by construction. This asserts the premise that
    argument rests on, rather than trusting it."""
    from pathlib import Path

    root = Path(scan_secrets.__file__).resolve().parents[1]
    shipped, where = _shipped(root)

    for name in (".env", ".capture_salt"):
        assert name not in shipped, f"{name} would ship ({where})"
    assert not [p for p in shipped if p.endswith((".wav", ".opus"))], f"raw media ships ({where})"


def test_the_fabricating_frontend_is_not_in_the_submission():
    """`legacy/frontend/` was a dashboard shell driven entirely by generated placeholder data.
    A judge opening fabricated data inside a submission that argues "never present generated
    data as real" is the one integrity risk this project cannot absorb. Removed 2026-08-30."""
    from pathlib import Path

    root = Path(scan_secrets.__file__).resolve().parents[1]
    shipped, _ = _shipped(root)

    assert not [p for p in shipped if p.startswith("legacy/frontend/")]
    assert not (root / "legacy" / "frontend").exists()
    # the rest of legacy/ is still preserved and disclosed
    assert [p for p in shipped if p.startswith("legacy/")], "all of legacy/ vanished"


def test_the_packaging_exclusions_are_declared():
    from pathlib import Path

    root = Path(scan_secrets.__file__).resolve().parents[1]
    attrs = (root / ".gitattributes").read_text(encoding="utf-8")

    for name in (".env", ".capture_salt"):
        assert f"{name}" in attrs and "export-ignore" in attrs


# ------------------------------------------------- a check that always fails is a check nobody reads

REPO = Path(__file__).resolve().parents[1]


def _scan(root):
    import subprocess
    import sys

    return subprocess.run([sys.executable, str(REPO / "scripts/scan_secrets.py"),
                           "--root", str(root)], capture_output=True, text=True)


def _git_repo(tmp_path, ignored: bool):
    import subprocess

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH\n", encoding="utf-8")
    if ignored:
        (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    return tmp_path


def test_a_git_ignored_env_file_does_not_fail_the_scan(tmp_path):
    """`make archive` builds from `git archive HEAD`, so an ignored file cannot enter the zip by
    construction. Failing for it taught the author that `make scan` always fails, which is how a
    security check stops being read."""
    done = _scan(_git_repo(tmp_path, ignored=True))

    assert done.returncode == 0
    assert "clean" in done.stdout


def test_it_is_reported_even_when_it_is_allowed(tmp_path):
    """Silence would be indistinguishable from not having looked."""
    done = _scan(_git_repo(tmp_path, ignored=True))

    assert ".env" in done.stdout
    assert "cannot reach the archive" in done.stdout


def test_an_env_file_that_is_NOT_ignored_still_fails(tmp_path):
    """The property actually worth protecting. If `.env` ever became trackable, this must stop
    the archive."""
    done = _scan(_git_repo(tmp_path, ignored=False))

    assert done.returncode == 1
    assert "must not ship" in done.stderr


def test_a_secret_in_a_project_file_always_fails(tmp_path):
    """Nothing about the git-ignore rule may soften this: a key in tracked source is a leak."""
    _git_repo(tmp_path, ignored=True)
    (tmp_path / "leaked.py").write_text(
        'key = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH"\n', encoding="utf-8")

    done = _scan(tmp_path)

    assert done.returncode == 1
    assert "SECRET IN A PROJECT FILE" in done.stderr


def test_outside_a_git_checkout_nothing_is_excused(tmp_path):
    """The extracted archive has no git. There, a local-only file being present is a real
    failure, and `is_git_ignored` returning False is what produces that."""
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH\n", encoding="utf-8")

    done = _scan(tmp_path)

    assert done.returncode == 1


# ---------------------------------------------------------- history, not just the working tree

def test_a_secret_removed_in_a_later_commit_is_still_found(tmp_path):
    """Making a repository public exposes every version of every file. A key committed once and
    deleted in the next commit is still in the pack, and `git log --name-only` cannot see it
    because the leak is in the content, not the filename."""
    import subprocess
    import sys

    run = lambda *a: subprocess.run(a, cwd=tmp_path, capture_output=True, text=True, check=False)
    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (tmp_path / "config.py").write_text(
        'KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGH"\n', encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "oops")
    (tmp_path / "config.py").write_text('KEY = os.getenv("K")\n', encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "removed")

    done = subprocess.run([sys.executable, str(REPO / "scripts/scan_secrets.py"), "--history"],
                          cwd=tmp_path, capture_output=True, text=True)

    assert done.returncode == 1
    assert "SECRET IN GIT HISTORY" in done.stderr
    assert "config.py@" in done.stderr


def test_this_repository_has_a_clean_history():
    """The result that matters before the repository is made public. Re-run rather than trusted:
    it takes under a second."""
    import subprocess
    import sys

    done = subprocess.run([sys.executable, str(REPO / "scripts/scan_secrets.py"), "--history"],
                          cwd=REPO, capture_output=True, text=True, timeout=300)

    assert done.returncode == 0, done.stderr[-1500:]
    assert "history clean" in done.stdout


def test_the_scanner_own_test_fixtures_do_not_trip_the_history_scan():
    """This file is full of synthetic keys on purpose. It is allowlisted by name, and if that
    ever stops working the history scan turns into permanent noise."""
    source = (REPO / "scripts/scan_secrets.py").read_text(encoding="utf-8")

    assert "Path(path).name in ALLOWLIST" in source
