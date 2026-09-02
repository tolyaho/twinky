"""The gold-label confirmation tool.

The flag it flips is the difference between "a person checked this" and "a model wrote this and
nobody looked". Everything here is about not letting that flag become cheap — and every test runs
against copies, never the committed labels.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def gold(tmp_path, monkeypatch):
    """A throwaway copy. The real `evals/gold/` is never written by a test."""
    import confirm_gold

    target = tmp_path / "gold"
    shutil.copytree(ROOT / "evals/gold", target)
    monkeypatch.setattr(confirm_gold, "GOLD", target)
    return target


def _doc(gold, case):
    return json.loads((gold / f"{case}.json").read_text(encoding="utf-8"))


def test_confirming_sets_the_flag_and_records_who(gold):
    import confirm_gold

    assert confirm_gold.main(["--confirm", "c05_warning_no_cause", "--by", "A. Person"]) == 0

    doc = _doc(gold, "c05_warning_no_cause")
    assert doc["reviewed"] is True
    assert doc["reviewed_by"] == "A. Person"


def test_disagreeing_is_recorded_rather_than_silently_dropped(gold):
    """A label a reviewer rejected is information. Leaving it `false` would look identical to a
    label nobody read."""
    import confirm_gold

    confirm_gold.main(["--disagree", "c11_sarcasm_mockery", "--by", "A. Person",
                       "--note", "the cause is the clip at 4:12"])

    doc = _doc(gold, "c11_sarcasm_mockery")
    assert doc["reviewed"] == "disagreed"
    assert doc["review_note"] == "the cause is the clip at 4:12"


def test_it_touches_nothing_but_the_review_fields(gold):
    import confirm_gold

    before = _doc(gold, "c01_word_puzzle_amethyst")
    confirm_gold.main(["--confirm", "c01_word_puzzle_amethyst", "--by", "A. Person"])
    after = _doc(gold, "c01_word_puzzle_amethyst")

    for key in ("case_id", "fixture", "window_ms", "gold_signals", "must_abstain",
                "label_provenance"):
        assert after[key] == before[key], f"{key} was modified"


def test_an_anonymous_confirmation_is_refused(gold):
    import confirm_gold

    assert confirm_gold.main(["--confirm", "c05_warning_no_cause"]) == 2
    assert _doc(gold, "c05_warning_no_cause")["reviewed"] is False


def test_an_unknown_case_is_refused_rather_than_created(gold):
    import confirm_gold

    assert confirm_gold.main(["--confirm", "c99_invented", "--by", "A. Person"]) == 2
    assert not (gold / "c99_invented.json").exists()


def test_there_is_no_way_to_confirm_everything_at_once():
    """Eleven labels behind one keystroke is how a review becomes a rubber stamp. The flag exists
    to separate a review that happened from one that was asserted."""
    source = (ROOT / "scripts/confirm_gold.py").read_text(encoding="utf-8")

    assert '"--all"' not in source
    assert "no `--all`" in source, "the omission is deliberate and should say so"


def test_the_committed_labels_are_still_unconfirmed():
    """If this ever fails, either a person really did review them — in which case update the
    documents that say otherwise — or something confirmed them automatically, which is worse."""
    import glob

    unreviewed = [f for f in glob.glob(str(ROOT / "evals/gold/*.json"))
                  if json.loads(Path(f).read_text(encoding="utf-8")).get("reviewed") is False]

    assert len(unreviewed) == 11
    assert "reviewed" in (ROOT / "README.md").read_text(encoding="utf-8")
