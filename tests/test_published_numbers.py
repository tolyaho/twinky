"""Every number a judge reads must equal the number the evaluation produced.

The results table appears in five places — README, SUBMISSION, the changelog, the shot list, and
`evidence/report.md` — and it has already been hand-propagated twice, once when the measurement
first landed and once when a repair moved the baseline from 20 cards to 21. Hand-propagation is
exactly where a stale number survives: the document still reads plausibly, and nothing fails.

`evidence/summary.json` is the machine-readable twin of the printed table, written by the same
`aggregate()` that writes `report.md`, so it is the single source of truth here.

Note the vacuity guards below. A regex that stops matching after a heading is renamed would make
this file pass while checking nothing — which is precisely how the old Makefile `grep` scan and
the pre-2026-08-30 secret scan both gave false assurance.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "evidence" / "summary.json"
LEDGER = REPO / "COST_LEDGER.md"

DOCS = ["README.md", "SUBMISSION.md", "docs/IMPROVEMENT_CHANGELOG.md", "video/SHOTLIST.md"]

# | system | cards | trigger accuracy | unmatched | unsupported | recall |
# `\**` absorbs bold markers and `[¹²³*†]*` absorbs footnote markers — the ablation row carries
# one, and without it this regex silently matched only two of the three systems. That is what the
# vacuity test below exists to catch, and it caught it on the first run.
_CELL = r"\s*\**([\d.]+)[¹²³*†]*\**\s*\|"
ROW = re.compile(
    r"^\|\s*\**([A-Za-z_ —(),-]+?)\**\s*\|\s*(\d+)\s*\|" + _CELL + _CELL + _CELL +
    r"\s*\**([\d.]+)[¹²³*†]*\**",
    re.M)

# How each document labels the three systems.
ALIAS = {
    "agent": "agent",
    "baseline": "baseline",
    "baseline — one prompt, same events": "baseline",
    "baseline — single prompt, same events": "baseline",
    "baseline (single prompt, same events)": "baseline",
    "ablation (chat only)": "ablation_chat_only",
    "ablation (chat only, diagnostic)": "ablation_chat_only",
    "ablation — chat only, diagnostic": "ablation_chat_only",
}

FIELDS = ["cards", "trigger_accuracy", "unmatched_rate", "unsupported_rate", "signal_recall"]


def truth():
    if not SUMMARY.exists():
        pytest.skip("no eval has been run; nothing is published yet")
    return json.loads(SUMMARY.read_text(encoding="utf-8"))["systems"]


def claims(doc):
    """Every results row in one document, as (label, system, values)."""
    out = []
    for m in ROW.finditer((REPO / doc).read_text(encoding="utf-8")):
        label = m.group(1).strip()
        system = ALIAS.get(label)
        if system is None:
            continue
        out.append((label, system,
                    [int(m.group(2))] + [float(m.group(i)) for i in (3, 4, 5, 6)]))
    return out


@pytest.mark.parametrize("doc", DOCS)
def test_every_published_row_matches_the_evaluation(doc):
    systems = truth()

    for label, system, values in claims(doc):
        expected = [systems[system][f] for f in FIELDS]
        for field, got, want in zip(FIELDS, values, expected):
            assert abs(got - want) < 5e-4, (
                f"{doc} claims {label} {field}={got}, evaluation says {want:.3f}")


@pytest.mark.parametrize("doc", DOCS)
def test_the_check_above_is_not_vacuous(doc):
    """If a heading is reworded so the regex stops matching, the test above passes while
    verifying nothing. Every document that carries the table must still carry it."""
    found = claims(doc)

    assert found, f"{doc} no longer has a parseable results table — the consistency check is dead"
    assert {s for _, s, _ in found} == {"agent", "baseline", "ablation_chat_only"}, (
        f"{doc} is missing a system row: {sorted({s for _, s, _ in found})}")


def test_all_three_systems_are_covered_by_the_summary():
    assert set(truth()) == {"agent", "baseline", "ablation_chat_only"}


def test_the_quoted_cost_matches_the_ledger():
    """`$0.39` appears in SUBMISSION.md and the shot list. The ledger is authoritative."""
    totals = re.findall(r"running_total=([\d.]+)", LEDGER.read_text(encoding="utf-8"))
    assert totals, "the ledger states no running total"
    ledger_total = float(totals[-1])

    quoted = set()
    for doc in DOCS + ["docs/REPRODUCTION.md"]:
        for m in re.finditer(r"\*\*\$([\d.]+) total\*\*|\$([\d.]+)\*\* total",
                             (REPO / doc).read_text(encoding="utf-8")):
            quoted.add(float(m.group(1) or m.group(2)))

    for value in quoted:
        assert abs(value - ledger_total) < 5e-3, (
            f"a document quotes ${value:.2f} total; COST_LEDGER.md says ${ledger_total:.2f}")


def test_the_report_and_the_summary_agree():
    """The two artifacts `make eval` writes are produced by the same aggregate(), but they are
    written separately — so this asserts they did not diverge."""
    report = (REPO / "evidence" / "report.md").read_text(encoding="utf-8")
    systems = truth()

    for label, system, values in [(lbl, sysname, vals)
                                  for lbl, sysname, vals in _report_rows(report)]:
        expected = [systems[system][f] for f in FIELDS]
        for field, got, want in zip(FIELDS, values, expected):
            assert abs(got - want) < 5e-4, f"report.md {label} {field}={got}, summary says {want}"


def _report_rows(report):
    rows = []
    for m in re.finditer(r"^\|\s*(\w[\w_]*)\s*\|\s*\d+\s*\|\s*(\d+)\s*\|"
                         r"\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)",
                         report, re.M):
        name = m.group(1)
        if name in ("agent", "baseline", "ablation_chat_only"):
            rows.append((name, name,
                         [int(m.group(2))] + [float(m.group(i)) for i in (3, 4, 5, 6)]))
    return rows


def test_the_report_row_check_is_not_vacuous():
    report = (REPO / "evidence" / "report.md").read_text(encoding="utf-8")

    assert len(_report_rows(report)) == 3, "report.md no longer has three parseable system rows"


# ------------------------------------------------------------ removed experiment #4, item H1
# Experiments #2 and #3 both ship their evidence — `evidence/grounded/` and the arm scorer — so
# every figure quoted for them can be recomputed. Experiment #4 was published from a run whose
# output went to a temp directory that no longer exists, which left a dozen figures in the
# changelog with nothing behind them but this file's word. `evidence/h1/` closes that: the run
# reproduces from the committed cache at 46 hits and 0 misses, and the numbers are read out of it
# here rather than remembered.

H1 = REPO / "evidence" / "h1"


def _agent_trigger_sources(predictions: Path):
    """Triggers RESOLVED against the fixture, not read off the model's claimed `kind`.

    A card that says `kind: "speech"` over a chat id is the failure being measured, so a census
    that trusts the claim cannot see it — the published table would have read 18 speech triggers
    where there are none.
    """
    import collections
    import sys

    sys.path[:0] = [str(REPO), str(REPO / "src")]
    from evals.run_eval import FIXTURES_DIR, load_cases
    from ts.ingest.replay import load_fixture

    types = {}
    for case in load_cases("all"):
        for event in load_fixture(FIXTURES_DIR / case["fixture"]).events:
            types[event.event_id] = event.type

    counts, codes = collections.Counter(), collections.Counter()
    for run in json.loads(predictions.read_text(encoding="utf-8")):
        if run["system"] != "agent":
            continue
        for card in run["cards"]:
            if card.get("status") == "abstained":
                counts["abstained"] += 1
            else:
                event_id = (card.get("trigger") or {}).get("event_id")
                counts["unknown" if event_id in (None, "unknown") else
                       {"chat_message": "chat", "transcript_segment": "speech",
                        "frame_caption": "frame"}.get(types.get(event_id), "absent")] += 1
            for violation in (card.get("gate") or {}).get("violations") or []:
                codes[violation if isinstance(violation, str) else violation.get("code")] += 1
    return counts, codes


def test_the_h1_arm_reproduces_from_the_committed_cache():
    """A removed experiment nobody can re-run is an assertion. This one runs with no key."""
    assert (H1 / "summary.json").is_file(), "evidence/h1/ is missing; regenerate it"
    shipped = json.loads(SUMMARY.read_text(encoding="utf-8"))["systems"]["agent"]
    h1 = json.loads((H1 / "summary.json").read_text(encoding="utf-8"))["systems"]["agent"]

    assert shipped["trigger_accuracy"] == 0.5 and h1["trigger_accuracy"] == 0.0
    assert h1["unsupported_rate"] == 1.0
    assert h1["signal_recall"] == shipped["signal_recall"], "recall did not move; the changelog says so"


def test_the_h1_arm_left_the_frozen_systems_alone():
    """The one thing that could not be undone. Both must still produce their published figures."""
    for system, accuracy in (("baseline", 0.0), ("ablation_chat_only", 1.0)):
        for path in (SUMMARY, H1 / "summary.json"):
            got = json.loads(path.read_text(encoding="utf-8"))["systems"][system]
            assert got["trigger_accuracy"] == accuracy, f"{system} moved in {path.parent.name}"


def test_the_changelog_quotes_the_trigger_table_it_measured():
    """Twelve figures in Removed experiment #4, every one recomputed from `evidence/h1/`."""
    before, before_codes = _agent_trigger_sources(REPO / "evidence" / "predictions.json")
    after, after_codes = _agent_trigger_sources(H1 / "predictions.json")

    # The finding itself: every honest response went to zero and circular triggers nearly doubled.
    assert before["abstained"] == 1 and after["abstained"] == 0
    assert before["unknown"] == 4 and after["unknown"] == 0
    assert before["speech"] == 4 and after["speech"] == 0
    assert before["frame"] == 0 and after["frame"] == 1
    assert before["chat"] == 13 and after["chat"] == 24
    assert before_codes["E_CIRCULAR_EVIDENCE"] == 8
    assert after_codes["E_CIRCULAR_EVIDENCE"] == 25

    changelog = (REPO / "docs/IMPROVEMENT_CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("Removed experiment #4", 1)[1]
    for row, b, a in (("abstained", 1, 0), ("a real speech id", 4, 0),
                      ("a real frame id", 0, 1)):
        line = next((l for l in section.splitlines() if l.startswith(f"| {row}")), None)
        assert line, f"the trigger table lost its `{row}` row"
        assert re.findall(r"\d+", line) == [str(b), str(a)], f"`{row}` row no longer measured"
