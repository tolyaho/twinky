"""Guards on the documents that are themselves deliverables.

A reproduction guide that names a command which does not exist is worse than no guide: it fails
the reviewer at the one step that decides whether the project is scored at all. These tests are
cheap and they catch drift the moment a target is renamed.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
REPRODUCTION = REPO / "docs" / "REPRODUCTION.md"
MAKEFILE = REPO / "Makefile"

# Only commands count: inline code, or a line inside a fenced block. Matching bare prose read
# "make the design look smaller" as a target named `the`.
MAKE_CALL = re.compile(r"`make ([a-z][a-z-]*)|^make ([a-z][a-z-]*)", re.M)
DOCS = [README, REPRODUCTION, REPO / "docs" / "PRE_EXISTING.md"]


def make_targets():
    return set(re.findall(r"^([a-z][a-z-]*):", MAKEFILE.read_text(encoding="utf-8"), re.M))


@pytest.mark.parametrize("doc", [README, REPRODUCTION], ids=lambda p: p.name)
def test_every_documented_make_target_exists(doc):
    targets = make_targets()
    named = {name for pair in MAKE_CALL.findall(doc.read_text(encoding="utf-8"))
             for name in pair if name}

    assert named, f"{doc.name} documents no commands"
    assert named <= targets, f"{doc.name} names missing targets: {sorted(named - targets)}"


def test_the_package_declares_the_src_layout():
    """Without this the documented `python -m ts.cli` only runs with PYTHONPATH=src, which is
    how the pipeline silently failed from a clean clone."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")

    assert 'package-dir = { "" = "src" }' in pyproject
    assert "install -e ." in MAKEFILE.read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_no_placeholder_survives_unlabelled(doc):
    """Bracketed placeholders are allowed — a fabricated number is not. Anything bracketed must
    be an obvious placeholder, never a value dressed up as measured."""
    text = doc.read_text(encoding="utf-8")

    for placeholder in re.findall(r"\[([A-Z_]{3,})\]", text):
        assert placeholder in {"TBD", "NAME", "VERSION", "REPO_URL", "UNVERIFIED"}, placeholder


def test_the_readme_status_section_is_honest_above_the_fold():
    """This test has tracked the truth three times: no fixture -> unmeasured -> measured but
    mixed. What it guards is constant — the first paragraph a judge reads states the real
    standing, including the parts that count against us, rather than burying them."""
    head = README.read_text(encoding="utf-8").split("## 1.")[0].lower()

    # the reproduction claim, which is the pre-scoring gate
    assert "cache hits" in head and "0 api calls" in head
    # the result is mixed and says so; a clean-sweep claim here would be the tell
    assert "worst unsupported-card rate" in head
    # gold labels are model-drafted and unconfirmed, and that is not buried
    assert "not yet author-confirmed" in head


def test_the_reproduction_guide_documents_the_current_exit_code():
    text = REPRODUCTION.read_text(encoding="utf-8")

    assert "exit `3`" in text
    assert "no API keys" in text


def test_the_documented_test_count_is_the_real_one(request):
    """The first number a reviewer checks is the one in the guide. Letting it drift by one added
    test is how a document stops being trustworthy."""
    if request.config.option.keyword or request.config.option.markexpr:
        pytest.skip("suite was filtered; the documented count refers to a full run")
    # A named file collects thirty-odd and would fail this for the wrong reason.
    if len(request.session.items) < 100:
        pytest.skip("documented count needs the full suite; run `make test`")

    documented = re.search(r"\*\*(\d+) passed", REPRODUCTION.read_text(encoding="utf-8"))

    assert documented, "REPRODUCTION.md no longer states a measured test count"
    assert int(documented.group(1)) == len(request.session.items)


def test_the_guide_does_not_promise_that_dotenv_is_read(request):
    """Nothing calls `load_dotenv`, so telling a reader to fill `.env` sends them into a failure
    that looks like a bad key. If that ever changes, change this test with it."""
    repo = REPO
    call_sites = 0
    for path in list(repo.glob("src/**/*.py")) + list(repo.glob("evals/*.py")) \
            + list(repo.glob("scripts/*.py")):
        call_sites += path.read_text(encoding="utf-8").count("load_dotenv")

    guide = REPRODUCTION.read_text(encoding="utf-8")
    if call_sites == 0:
        assert "cp .env.example .env" not in guide
        # Nothing reads .env, so the guide must tell the reader to export the variables. The
        # name tracks the provider actually used; it was DEEPSEEK_API_KEY before the switch.
        assert "export TS_LLM_API_KEY" in guide


# --------------------------------------------------------------------------- claims vs. tree
ARCHITECTURE = REPO / "docs" / "ARCHITECTURE.md"

# Every path the architecture diagram marks with a tick must exist. The diagram claimed a
# summary hierarchy that no module implements, and the README repeated the claim.
CLAIMED_MODULES = [
    "src/ts/ingest/replay.py", "src/ts/events.py", "src/ts/workflow/reduce.py",
    "src/ts/workflow/tools.py", "src/ts/workflow/agent.py", "src/ts/baseline",
    "src/ts/provenance.py", "src/ts/report/serve.py", "src/ts/report/debrief.py",
    "src/ts/workflow/trace.py", "src/ts/cache.py", "src/ts/clock.py", "src/ts/providers",
    "evals", "scripts/scan_secrets.py",
]


@pytest.mark.parametrize("relative", CLAIMED_MODULES)
def test_every_ticked_node_exists(relative):
    assert (REPO / relative).exists()
    assert relative.split("/")[-1].replace(".py", "") in ARCHITECTURE.read_text(encoding="utf-8") \
        or relative in ARCHITECTURE.read_text(encoding="utf-8")


def test_the_summary_hierarchy_is_declared_unbuilt_while_it_is_unbuilt():
    """It was claimed as implemented in two documents at once. If it ever gets built, this test
    is the thing that reminds you to update both."""
    implemented = any(
        "summary" in path.read_text(encoding="utf-8").lower().replace("result_summary", "")
        and "hierarch" in path.read_text(encoding="utf-8").lower()
        for path in (REPO / "src").rglob("*.py"))

    if not implemented:
        assert "is NOT built" in ARCHITECTURE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        assert "| **no** |" in readme
        assert "not implemented" in readme


def test_the_agents_four_tools_are_the_four_the_docs_name():
    from ts.workflow.agent import ALLOWED_TOOLS

    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert f"{len(ALLOWED_TOOLS)} read-only" in architecture
    for tool in ALLOWED_TOOLS:
        assert tool in README.read_text(encoding="utf-8"), tool


def _full_run_only(request):
    """These two guards compare a documented count against the collected suite, so they are only
    meaningful when the whole suite was collected. Running `pytest tests/test_docs.py` collects
    thirty-odd and would fail them for the wrong reason — which is a test that cries wolf, and a
    judge running one file is exactly the person who should not see a red herring."""
    import pytest

    if len(request.session.items) < 100:
        pytest.skip("test-count guard needs the full suite; run `make test`")


def test_the_shot_list_quotes_the_real_test_count(request):
    """It went stale by a hundred tests and described a two-column page that no longer existed.
    A shot list is filmed from once, under time pressure, and nobody re-checks it on the day."""
    import re

    _full_run_only(request)
    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")
    quoted = re.findall(r"(\d+) passed", shots)

    assert quoted, "the shot list no longer states a test count"
    for n in quoted:
        assert int(n) == len(request.session.items), \
            f"the shot list says {n} passed; the suite has {len(request.session.items)}"


def test_the_shot_list_matches_the_published_results_table():
    """Every figure spoken on camera has to be one `make eval` reproduces."""
    import re

    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")
    report = (REPO / "evidence/report.md").read_text(encoding="utf-8")

    for system, recall in [("agent", "0.182"), ("baseline", "0.091")]:
        row = next(line for line in report.splitlines()
                   if line.startswith(f"| {system} |"))
        for figure in re.findall(r"\d\.\d{3}", row):
            assert figure in shots, f"{system} {figure} is in the report and not in the shot list"
        assert recall in shots


def test_the_shot_list_does_not_describe_the_old_interface():
    """The page has three zones, a Board/Signals/Questions control and live counts. A shot list
    describing the two-column build would have the author filming a product that is gone."""
    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")

    for gone in ["the card rail — 13 windows", "Grounded signals"]:
        assert gone not in shots
    for present in ["Questions", "Tier 0", "agent graph", "this minute so far", "violet × 27"]:
        assert present in shots, f"the shot list never shows {present}"


def test_the_shot_list_calls_the_grounded_arm_a_failure():
    """It is a removed experiment with a measured result. Describing it as shipped would be the
    one unrecoverable claim in the video."""
    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")

    assert "tried, measured and not adopted" in shots
    assert "and it lost" in shots
    assert "I did not apply it" not in shots, "that sentence is no longer true"


# ------------------------------------------------------ the first two documents a judge reads
# They described a two-column page and 33 trajectories for about fifteen iterations after both
# stopped being true. The shot list rotted the same way. These stop it happening silently.

def test_the_trajectory_count_is_the_real_one():
    import glob

    actual = len(glob.glob(str(REPO / "trajectories/product-agent/*.json")))
    for name in ("README.md", "SUBMISSION.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert f"**{actual} real runs**" in text, f"{name} misstates the trajectory count"
        assert "33 real runs" not in text


def test_the_documents_describe_the_interface_that_exists():
    """Three zones with a Board/Signals/Questions control, not two columns."""
    submission = (REPO / "SUBMISSION.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    for text in (submission, readme):
        assert "chat on the left, signals on the right" not in text
    assert "Three zones" in submission and "three zones" in readme
    assert "Board | Signals | Questions" in readme
    for feature in ("Tier 0", "agent graph", "NEEDS A LOOK"):
        assert feature in submission, f"{feature} is not mentioned in the submission"


def test_the_rolled_back_experiments_are_in_the_submission():
    """Three things built, measured and declined. That is the part of engineering that usually
    leaves no trace, and it was invisible in the document a judge reads first."""
    submission = (REPO / "SUBMISSION.md").read_text(encoding="utf-8")
    changelog = (REPO / "docs/IMPROVEMENT_CHANGELOG.md").read_text(encoding="utf-8")

    assert changelog.count("## Removed experiment") >= 2
    assert "tried, measured, and rolled back" in submission
    for evidence in ("28 dB", "0 → 4", "0.583"):
        assert evidence in submission, f"the {evidence} result is missing"


def test_the_grouping_figures_in_the_submission_are_the_measured_ones():
    """Quoted in `SUBMISSION.md`, so they have to be what the scorer prints today."""
    import sys

    sys.path.insert(0, str(REPO))
    from evals.grouping.score_arms import run

    overall = run()["overall"]
    submission = (REPO / "SUBMISSION.md").read_text(encoding="utf-8")

    for arm in ("A · exact canonical", "B · token + prefix"):
        for key in ("precision", "recall", "f1"):
            assert f"{overall[arm][key]:.3f}" in submission, \
                f"{arm} {key} = {overall[arm][key]:.3f} is not in SUBMISSION.md"


def test_the_architecture_names_every_module_it_claims_to_cover():
    """"One file per node" is the claim. Six modules landed after the diagram was drawn and none
    of them appeared in it, which makes the diagram a picture of a system that used to exist."""
    architecture = (REPO / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    modules = sorted(p.name for p in (REPO / "src/ts/report").glob("*.py")
                     if p.name not in {"__init__.py", "poll.py", "debrief.py"})

    missing = [m for m in modules if m not in architecture]
    assert not missing, f"the diagram does not mention {missing}"
    for module in ("live_chat.py", "live.py"):
        assert module in architecture


def test_the_reproduction_guide_documents_what_the_submission_points_at():
    """SUBMISSION.md tells a judge to run these. The file whose entire job is reproduction has to
    know about them."""
    guide = (REPO / "docs/REPRODUCTION.md").read_text(encoding="utf-8")

    for command in ("--grounded", "score_arms", "make graph"):
        assert command in guide, f"{command} is promised elsewhere and undocumented here"


def test_the_reproduction_guide_quotes_the_measured_grouping_figures():
    import sys

    sys.path.insert(0, str(REPO))
    from evals.grouping.score_arms import run

    overall = run()["overall"]
    guide = (REPO / "docs/REPRODUCTION.md").read_text(encoding="utf-8")

    for arm in ("A · exact canonical", "B · token + prefix"):
        assert f"{overall[arm]['precision']:.3f} / {overall[arm]['recall']:.3f}" in guide \
            or f"{overall[arm]['precision']:.3f}" in guide


def test_the_guide_describes_the_scanner_as_it_now_behaves():
    """It said a local `.env` was fatal. It is reported and allowed when git confirms it is
    ignored, and the guide has to say which, or the next person reads a pass as a bug."""
    # Prose wraps. Assert against the words, not against where the line happened to break —
    # this is the fourth time a guard has failed on a newline rather than on the content.
    guide = " ".join((REPO / "docs/REPRODUCTION.md").read_text(encoding="utf-8").split())

    assert "cannot enter the zip by construction" in guide
    assert "outside a git checkout" in guide


def test_the_coding_agent_disclosure_states_the_real_trajectory_count():
    """It said the directory was "empty today because no run has been recorded yet". That was
    true when written and false for most of the project's life — in the one document whose whole
    purpose is accurate attribution."""
    import glob

    disclosure = (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8")
    actual = len(glob.glob(str(REPO / "trajectories/product-agent/*.json")))

    assert f"**{actual} trajectories**" in disclosure
    assert "empty today" not in disclosure.split("*(This section previously read")[0]


def test_the_disclosure_records_failures_as_well_as_output():
    """A disclosure that only claims productivity is not a disclosure."""
    disclosure = " ".join(
        (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8").split())

    for found in ("BROKEN — NOT A RESULT", "Keyless reproduction was silently broken",
                  "could never pass on a developer machine",
                  "flagged the product's own best output"):
        assert found in disclosure, f"the disclosure no longer mentions: {found}"


def test_the_disclosure_does_not_claim_zero_spend():
    """Paid calls happened. Ten of them, itemised."""
    disclosure = " ".join(
        (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8").split())
    ledger = (REPO / "COST_LEDGER.md").read_text(encoding="utf-8")

    assert "kept paid calls at zero" not in disclosure
    import re
    total = re.findall(r"running_total=([0-9.]+)", ledger)[-1]
    assert f"${total}" in disclosure


def test_no_risk_number_is_used_twice():
    """`RISKS.md` says numbers are stable because other documents cite them. Two rows added on
    the same day reused 36 and 37, which made the critical-path summary ambiguous about which
    #36 it meant — in the list the author works from in the final hours."""
    import collections
    import re

    numbers = re.findall(r"^\| (\d+) \|", (REPO / "RISKS.md").read_text(encoding="utf-8"), re.M)
    duplicates = [n for n, count in collections.Counter(numbers).items() if count > 1]

    assert not duplicates, f"risk numbers reused: {duplicates}"
    assert len(numbers) >= 40


def test_the_critical_path_points_at_risks_that_exist():
    """The summary is the author's checklist. A `#n` in it that resolves to the wrong row, or to
    no row, is worse than no reference."""
    import re

    text = (REPO / "RISKS.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^\| (\d+) \|", text, re.M))
    summary = text.split("## P0", 1)[0]

    for cited in re.findall(r"#(\d+)", summary):
        assert cited in defined, f"the critical path cites #{cited}, which has no row"


def test_the_four_author_blockers_are_all_tracked_and_open():
    """Video, gold labels, private repository, live credentials. If one of these is not open, it
    is either genuinely done — in which case say so everywhere — or it fell off the list."""
    text = (REPO / "RISKS.md").read_text(encoding="utf-8")

    # Table rows only. The prose summary mentions the same things and is not the record.
    rows = [l for l in text.splitlines() if l.startswith("| ") and not l.startswith("| # ")]
    for phrase in ("Video not started", "Gold labels are model-drafted",
                   "repository is private", "`.env` holds"):
        row = next((l for l in rows if phrase in l), None)
        assert row is not None, f"no risk row for: {phrase}"
        assert "OPEN" in row.upper(), f"{phrase} is no longer open — update the documents too"


def test_preflight_treats_an_unpushed_remote_as_a_blocker():
    """A public repository showing old work looks finished, which is worse than a private one:
    nobody thinks to check. Found when origin/main was 31 commits behind local while the risk
    register said the only remaining repository action was "make it public"."""
    source = (REPO / "scripts/preflight.py").read_text(encoding="utf-8")

    assert "PUSH BEFORE PUBLISHING" in source
    assert "origin/main..HEAD" in source
    risks = (REPO / "RISKS.md").read_text(encoding="utf-8")
    assert "pushed and then made public" in risks


def test_preflight_separates_blockers_from_stated_costs():
    """Unconfirmed gold labels are a cost the README already states, not a reason to stop. A
    checklist that cannot tell those apart gets ignored at 3am."""
    source = (REPO / "scripts/preflight.py").read_text(encoding="utf-8")

    assert "hard" in source and "TODO" in source
    assert "is not a blocker, only a cost" in source


def test_preflight_never_repairs_anything():
    """It reports. A checklist that fixes things is a checklist you stop reading."""
    source = (REPO / "scripts/preflight.py").read_text(encoding="utf-8")

    for mutating in ("git push", "git commit", "write_text", "unlink", "--confirm"):
        assert mutating not in source, f"preflight would perform {mutating!r}"


def test_a_network_check_that_cannot_run_says_so():
    """An offline check that silently passes is worse than one that admits it does not know."""
    source = (REPO / "scripts/preflight.py").read_text(encoding="utf-8")

    assert "cannot reach origin" in source
    assert "gh unavailable" in source


def test_preflight_does_not_block_on_an_untracked_capture():
    """Three partial captures appeared on disk mid-session. Blocking a submission on capture data
    that is correctly not committed is a false alarm, and a checklist that cries wolf once stops
    being read."""
    source = (REPO / "scripts/preflight.py").read_text(encoding="utf-8")

    assert '"/fixtures/" in l' in source
    assert "correctly not committed" in source
    assert "uncommitted source" in source


def _will_ship(path: str) -> bool:
    """True for a path git tracks and does not export-ignore, even if not committed yet.

    Without this, citing a newly added directory fails until the commit lands, which is a
    chicken-and-egg rather than a defect. It keeps the teeth: `.env.example` — the file that
    prompted this test — was tracked and un-ignored and still export-ignored, so `check-attr`
    reports it and it would still be caught.
    """
    import subprocess

    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path],
                             cwd=REPO, capture_output=True, text=True, timeout=30)
    if tracked.returncode != 0 or not tracked.stdout.strip():
        return False
    for candidate in tracked.stdout.split():
        attr = subprocess.run(["git", "check-attr", "export-ignore", "--", candidate],
                              cwd=REPO, capture_output=True, text=True, timeout=30)
        # `check-attr` prints `path: export-ignore: set|unset|unspecified`. `endswith("set")`
        # matches "unset" too, which rejected `.env.example` — the one path `-export-ignore`
        # exists to re-include. Compare the final field exactly.
        if attr.stdout.strip().rsplit(": ", 1)[-1] == "set":
            return False
    return True


def test_every_path_the_entry_documents_cite_exists_in_the_archive():
    """A judge reads `SUBMISSION.md`, `README.md` and `docs/REPRODUCTION.md` first and follows
    the paths in them. What matters is not whether a file exists in the working tree but whether
    it is in `git archive HEAD` — `.env.example` was tracked, un-ignored and still absent."""
    import re

    from conftest import archived_or_skip

    # Not `set()` on failure: inside the extracted archive there is no git, and an empty listing
    # would report every cited path as missing rather than admitting the question is unanswerable
    # from there.
    files = archived_or_skip()

    missing = []
    for name in ("SUBMISSION.md", "README.md", "docs/REPRODUCTION.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        cited = set(re.findall(r"`([A-Za-z0-9_][\w./-]*\.(?:md|py|json|csv|svg|css|js|toml))`",
                               text))
        cited |= set(re.findall(
            r"`((?:docs|evals|evidence|src|tests|video|trajectories|scripts)/[\w./-]*)`", text))
        for path in cited:
            p = path.rstrip("/")
            if p in files or any(f.startswith(p + "/") for f in files):
                continue
            if _will_ship(p):
                continue
            missing.append(f"{name} -> {path}")

    assert not missing, f"cited but not shipped: {sorted(set(missing))}"


def test_the_opening_shot_does_not_put_a_slur_on_camera():
    """Shot 2's window holds 79 messages and message 2 is a slur aimed at a named viewer. The
    unfiltered command put it second on screen in the submission's first product shot. Found by
    running the command, not by reading it."""
    import json
    import re

    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")
    assert "re.fullmatch" in shots, "shot 2 is unfiltered again"
    assert "70 are one-word guesses" in shots, "the reason must travel with the filter"

    slur = re.compile(r"\bretard|\bn[i1]gg|\bfag|\btrann|\bkys\b", re.I)
    shown = []
    fixture = REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl"
    for line in fixture.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if 1788074707878 <= d["ts_ms"] < 1788074767878 and \
                re.fullmatch(r"[A-Za-z']{3,20}", d["text"].strip()):
            shown.append(d["text"])

    assert len(shown) > 50, "the shot must still show the guess run"
    assert not [t for t in shown if slur.search(t)]


def test_the_filming_guidance_matches_the_fixtures():
    """The shot list tells the author how long the unfiltered feed can run before live chat shows
    what live chat shows. That is a measurement, so it has to keep matching the data."""
    import json
    import re
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from ts.ingest.replay import load_fixture
    from ts.report.board import windows

    slur = re.compile(r"\bretard\w*|\bn[i1]gg\w*|\bfag\w*|\btrann\w*|\bkys\b|\bcunt\w*", re.I)

    def flagged(name):
        rows = [json.loads(l) for l in
                (REPO / f"evals/fixtures/{name}/chat.jsonl").read_text(encoding="utf-8").splitlines()]
        return rows, [r for r in rows if slur.search(r.get("text") or "")]

    rows, hits = flagged("marlon_2026-08-30T0715")
    assert len(rows) == 1535 and not hits, "marlon is no longer the clean fixture the list claims"

    index = load_fixture(REPO / "evals/fixtures/stableronaldo_2026-08-30T0723")
    first_window = windows(index)[0]
    rows, hits = flagged("stableronaldo_2026-08-30T0723")
    in_shot = [h for h in hits if first_window[0] <= h["ts_ms"] < first_window[1]]
    assert not in_shot, "shot 4's window is no longer clean — the list says it is"

    shots = (REPO / "video/SHOTLIST.md").read_text(encoding="utf-8")
    assert "clean over all 1535 messages" in shots
    assert "window 0 is clean" in shots


def test_the_disclosure_scale_table_is_counted_not_remembered():
    """Every row of it had drifted. `Tests` said 623 against 702, `Risks tracked` 42 against 51,
    `Decisions` 303 against 414, `Commits` 129 against 165 — a table headed "for calibration"
    that miscalibrated by a third. It was the only published figure set with no guard, which is
    exactly why it was the one that rotted.

    Counted from the artifacts, with a tolerance of zero: these are counts, not estimates, and
    a disclosure that rounds its own scale is not disclosing.
    """
    import re
    import subprocess

    disclosure = (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| ([A-Z][^|]+?) +\| ([\d]+) \|$", disclosure, re.M))

    decisions = len(re.findall(r"^\| 20\d\d-\d\d-\d\d ",
                               (REPO / "DECISIONS.md").read_text(encoding="utf-8"), re.M))
    risks = len(set(re.findall(r"^\| ?(\d+) ?\|",
                               (REPO / "RISKS.md").read_text(encoding="utf-8"), re.M)))
    progress = (REPO / "PROGRESS.md").read_text(encoding="utf-8")
    iterations = max(int(n) for n in re.findall(r"^## Iteration (\d+)", progress, re.M))

    # Tolerances allow roughly one iteration of lag and nothing more: a table updated last
    # iteration is fine, a table updated fifty iterations ago is what this exists to catch. The
    # drift that prompted it was 30-40% on every row.
    for label, actual, slack in (("Decisions recorded with rationale", decisions, 8),
                                 ("Risks tracked", risks, 2),
                                 ("Iterations logged", iterations, 2)):
        assert label in rows, f"the scale table lost its `{label}` row"
        assert abs(int(rows[label]) - actual) <= slack, \
            f"disclosure says {label} = {rows[label]}; the file says {actual}"

    # Commits are counted from the window open, which is the disclosure's own definition. In an
    # archive there is no git and the question has no answer from here, so it is skipped rather
    # than guessed — the same rule as the four archive checks.
    done = subprocess.run(["git", "log", "--oneline", "--since=2026-08-28T15:00:00Z"],
                          cwd=REPO, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        return
    commits = len([l for l in done.stdout.splitlines() if l.strip()])
    assert abs(int(rows["Commits in the competition window"]) - commits) <= 1, \
        f"disclosure says {rows['Commits in the competition window']} commits; git says {commits}"


def test_the_iteration_prose_and_the_scale_table_agree():
    """The prose says how many iterations carry a heading; the table says how many there are.
    They were written months apart in the same file and both were wrong."""
    import re

    disclosure = (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8")
    headings = len(re.findall(r"^## Iteration ",
                              (REPO / "PROGRESS.md").read_text(encoding="utf-8"), re.M))

    stated = re.search(r"of which (\d+) carry a\s*\n?`## Iteration` heading", disclosure)
    assert stated, "the disclosure no longer says how many iterations carry a heading"
    assert abs(int(stated.group(1)) - headings) <= 2, \
        f"disclosure says {stated.group(1)} headings; PROGRESS.md has {headings}"
