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
