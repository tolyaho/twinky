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
