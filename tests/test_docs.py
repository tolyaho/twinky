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


def test_the_readme_states_that_results_are_not_measured_yet():
    """While the cache is empty the README must say so above the fold, not bury it."""
    head = README.read_text(encoding="utf-8").split("## 1.")[0]

    assert "no fixture has been recorded yet" in head.lower()
    assert "[TBD]" in head


def test_the_reproduction_guide_documents_the_current_exit_code():
    text = REPRODUCTION.read_text(encoding="utf-8")

    assert "exit `3`" in text
    assert "no API keys" in text


def test_the_documented_test_count_is_the_real_one(request):
    """The first number a reviewer checks is the one in the guide. Letting it drift by one added
    test is how a document stops being trustworthy."""
    if request.config.option.keyword or request.config.option.markexpr:
        pytest.skip("suite was filtered; the documented count refers to a full run")

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
        assert "export DEEPSEEK_API_KEY" in guide


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
