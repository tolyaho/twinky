"""Guards on the documents that make claims about the code.

A reproduction guide that names a command which does not exist is worse than no guide: it fails
the reader at the first step, and everything after it is now suspect. These tests are cheap and
they catch drift the moment a target is renamed.
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
DOCS = [README, REPRODUCTION, REPO / "docs" / "ARCHITECTURE.md"]


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
    """This test has tracked the truth four times: no fixture -> unmeasured -> measured but mixed
    -> mixed, with the agent no longer worst of three. What it guards is constant — the first
    paragraph anyone reads states the real standing, including the parts that count against us,
    rather than burying them."""
    head = README.read_text(encoding="utf-8").split("## 1.")[0].lower()

    # the reproduction claim, checkable by anyone for free
    assert "cache hits" in head and "0 api calls" in head
    # the result is mixed and says so; a clean-sweep claim here would be the tell. The agent
    # stopped being worst-of-three when the gate change landed, so the sentence moved with the
    # measurement rather than being quietly dropped.
    assert "loses the unsupported-card rate" in head
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


# ----------------------------------------------------------- the document anyone reads first
# It described a two-column page and 33 trajectories for about fifteen iterations after both
# stopped being true. These stop it happening silently.

def test_the_trajectory_count_is_the_real_one():
    import glob

    actual = len(glob.glob(str(REPO / "trajectories/product-agent/*.json")))
    text = README.read_text(encoding="utf-8")

    assert f"**{actual} real runs**" in text, "README.md misstates the trajectory count"
    assert "33 real runs" not in text


def test_the_readme_describes_the_interface_that_exists():
    """Three zones with a Board/Signals/Questions control, not two columns."""
    readme = README.read_text(encoding="utf-8")

    assert "chat on the left, signals on the right" not in readme
    assert "three zones" in readme
    assert "Board | Signals | Questions" in readme
    for feature in ("Tier 0", "NEEDS A LOOK"):
        assert feature in readme, f"{feature} is not mentioned in the README"


def test_the_rolled_back_experiments_are_recorded():
    """Three things built, measured and declined. That is the part of engineering that usually
    leaves no trace, so the log is the only place it survives."""
    changelog = (REPO / "docs/IMPROVEMENT_CHANGELOG.md").read_text(encoding="utf-8")

    assert changelog.count("## Removed experiment") >= 2
    for evidence in ("28 dB", "0.583"):
        assert evidence in changelog, f"the {evidence} result is missing"


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


def test_the_reproduction_guide_documents_what_the_readme_points_at():
    """The README tells a reader to run these. The file whose entire job is reproduction has to
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


def test_the_open_author_blockers_are_all_tracked_and_open():
    """Two live credential sets, the unconfirmed gold labels, and the pseudonymisation limit. If
    one of these is not open, it is either genuinely done — in which case say so everywhere — or
    it fell off the list. The submission-gate rows that used to sit here (the video, the private
    repository) are closed and were deliberately dropped; these four are the ones that outlive
    the reason they were first written down."""
    text = (REPO / "RISKS.md").read_text(encoding="utf-8")

    # Table rows only. The prose summary mentions the same things and is not the record.
    rows = [l for l in text.splitlines() if l.startswith("| ") and not l.startswith("| # ")]
    for phrase in ("Gold labels are model-drafted", "`.env` holds",
                   "Credentials pasted in the team Telegram group",
                   "Pseudonymisation covers the author field"):
        row = next((l for l in rows if phrase in l), None)
        assert row is not None, f"no risk row for: {phrase}"
        assert "OPEN" in row.upper(), f"{phrase} is no longer open — update the documents too"


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
    """Anyone arriving reads `README.md` and `docs/REPRODUCTION.md` first and follows the paths
    in them. What matters is not whether a file exists in the working tree but whether it is in
    `git archive HEAD` — `.env.example` was tracked, un-ignored and still absent."""
    import re

    from conftest import archived_or_skip

    # Not `set()` on failure: inside the extracted archive there is no git, and an empty listing
    # would report every cited path as missing rather than admitting the question is unanswerable
    # from there.
    files = archived_or_skip()

    missing = []
    for name in ("README.md", "docs/REPRODUCTION.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        cited = set(re.findall(r"`([A-Za-z0-9_][\w./-]*\.(?:md|py|json|csv|svg|css|js|toml))`",
                               text))
        cited |= set(re.findall(
            r"`((?:docs|evals|evidence|src|tests|reference|trajectories|scripts)/[\w./-]*)`",
            text))
        for path in cited:
            p = path.rstrip("/")
            if p in files or any(f.startswith(p + "/") for f in files):
                continue
            if _will_ship(p):
                continue
            missing.append(f"{name} -> {path}")

    assert not missing, f"cited but not shipped: {sorted(set(missing))}"


def test_the_demo_window_does_not_open_on_a_slur():
    """The default demo window holds 79 messages and message 2 is a slur aimed at a named viewer.
    Unfiltered, it lands second on screen the moment anyone runs `make demo` in front of another
    person. The word-guess filter is what keeps it off; this is the check that the filter still
    covers the window it was written for. Found by running the command, not by reading it."""
    import json
    import re

    slur = re.compile(r"\bretard|\bn[i1]gg|\bfag|\btrann|\bkys\b", re.I)
    shown = []
    fixture = REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl"
    for line in fixture.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if 1788074707878 <= d["ts_ms"] < 1788074767878 and \
                re.fullmatch(r"[A-Za-z']{3,20}", d["text"].strip()):
            shown.append(d["text"])

    assert len(shown) > 50, "the window must still show the guess run"
    assert not [t for t in shown if slur.search(t)]


def test_the_disclosure_scale_table_is_counted_not_remembered(request):
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
                               (REPO / "docs/archive/DECISIONS.md").read_text(encoding="utf-8"), re.M))
    risks = len(set(re.findall(r"^\| ?(\d+) ?\|",
                               (REPO / "RISKS.md").read_text(encoding="utf-8"), re.M)))
    progress = (REPO / "docs/archive/PROGRESS.md").read_text(encoding="utf-8")
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

    # The `Tests` row was outside this loop and drifted by nineteen without anything noticing,
    # while three rows beside it were held to a tolerance of two. A count the suite can answer
    # about itself has no business being remembered.
    if len(request.session.items) >= 100:
        assert int(rows["Tests"]) == len(request.session.items), \
            f'disclosure says Tests = {rows["Tests"]}; the suite has {len(request.session.items)}'

    # Commits are counted from the window open, which is the disclosure's own definition. In an
    # archive there is no git and the question has no answer from here, so it is skipped rather
    # than guessed — the same rule as the four archive checks.
    done = subprocess.run(["git", "log", "--oneline", "--since=2026-08-28T15:00:00Z"],
                          cwd=REPO, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        return
    commits = len([l for l in done.stdout.splitlines() if l.strip()])
    # Wider than the rows above, and not to make it pass. Those are counted from files the same
    # commit contains, so an exact answer exists to write down. This one is not: the count only
    # becomes true after the commit that records it, so writing it correctly means predicting
    # your own next commit, and every commit afterwards breaks it again. At a tolerance of one
    # the row is unsatisfiable by construction. Three keeps it a real check on a stale table —
    # the drift it was written for was thirty per cent — without asking for prophecy.
    assert abs(int(rows["Commits in the measured window"]) - commits) <= 3, \
        f"disclosure says {rows['Commits in the measured window']} commits; git says {commits}"


def test_the_iteration_prose_and_the_scale_table_agree():
    """The prose says how many iterations carry a heading; the table says how many there are.
    They were written months apart in the same file and both were wrong."""
    import re

    disclosure = (REPO / "trajectories/coding-agents/README.md").read_text(encoding="utf-8")
    headings = len(re.findall(r"^## Iteration ",
                              (REPO / "docs/archive/PROGRESS.md").read_text(encoding="utf-8"), re.M))

    stated = re.search(r"of which (\d+) carry a\s*\n?`## Iteration` heading", disclosure)
    assert stated, "the disclosure no longer says how many iterations carry a heading"
    assert abs(int(stated.group(1)) - headings) <= 2, \
        f"disclosure says {stated.group(1)} headings; PROGRESS.md has {headings}"


def test_no_documented_command_calls_an_interpreter_that_may_not_exist():
    """`python -m evals.run_eval …` appeared in sixteen places across four entry documents, and
    `python` is not a command on a stock macOS — `command not found`. `make setup` builds `.venv`
    and nothing tells the reader to activate it, so every one of those lines failed for anyone
    who followed the guide, including the author reading the shot list on camera.

    `python3 -c` on stdlib is left alone: it needs no installed package and it does exist. What
    is forbidden is `-m`, which needs this project importable.
    """
    import re

    # `python foo.py` is the same failure as `python -m foo` and the first version of this rule
    # missed it, because it only looked for `-m`. It survived in `evals/REVIEW_ME.md`, which is
    # the guide for the one author task that is cheap to finish.
    offenders = []
    for name in ("README.md", "docs/REPRODUCTION.md", "docs/ARCHITECTURE.md",
                 "docs/IMPROVEMENT_CHANGELOG.md",
                 "experiments/README.md", "trajectories/h1-arm/README.md",
                 "evals/REVIEW_ME.md", "evals/DATA.md"):
        path = REPO / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            script = re.search(r"(?<![\w./-])python3? +[\w./-]+\.py", line)
            if script:
                offenders.append(f"{name}: {line.strip()}")
            hit = re.search(r"(?<![\w./-])python3? -m (\w+)", line)
            # `venv`, `pip` and `ensurepip` are the exceptions and they are not arbitrary: they
            # are stdlib modules that run BEFORE the environment exists, so they cannot use the
            # interpreter inside it. The first version of this rule had no exemption, and the
            # blanket substitution it justified turned `python3 -m venv` into
            # `.venv/bin/python -m venv` in the setup instructions.
            if hit and hit.group(1) not in {"venv", "pip", "ensurepip"}:
                offenders.append(f"{name}: {line.strip()}")

    assert not offenders, ("these need `.venv/bin/python -m`, or they die with "
                           f"`command not found`:\n" + "\n".join(offenders))

    # The opposite error, and self-inflicted: the blanket substitution that fixed the above
    # rewrote `python3 -m venv` into `.venv/bin/python -m venv`, which asks the interpreter
    # inside the environment to create that environment. A bootstrap command cannot use the
    # thing it bootstraps.
    for name in ("README.md", "docs/REPRODUCTION.md", "docs/ARCHITECTURE.md"):
        path = REPO / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for impossible in (".venv/bin/python -m venv", ".venv/bin/pip install -r"):
                assert impossible not in text, f"{name} bootstraps with `{impossible}`"


def test_data_md_accounts_for_every_committed_fixture_directory():
    """`evals/fixtures/` holds 27 directories and every entry document says four broadcasts. The
    other 23 are a single `meta.json` each — captures that were never enriched, plus the
    synthetic scaffold — and nothing explained them, so a judge browsing the evaluation data met
    23 directories that look abandoned.

    Counted here rather than quoted, because the numbers in that section are the reason it is
    reassuring rather than hand-waving.
    """
    import json

    root = REPO / "evals/fixtures"
    dirs = [d for d in sorted(root.iterdir()) if d.is_dir()]
    enriched, capture_only = [], []
    for d in dirs:
        if d.name == "sample":
            continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        (enriched if meta.get("enriched") else capture_only).append(meta)

    data = (REPO / "evals/DATA.md").read_text(encoding="utf-8")
    assert f"| **enriched, evaluated** | {len(enriched)} |" in data
    assert f"| captured, never enriched | {len(capture_only)} |" in data

    channels = {m["fixture_id"].split("_")[0] for m in capture_only}
    messages = sum(m.get("chat_messages") or 0 for m in capture_only)
    assert f"**{len(channels)} channels, {messages:,} chat messages" in data, \
        f"DATA.md misstates the capture-only totals; measured {len(channels)} / {messages:,}"

    # The claim that costs the most if wrong: nothing but meta.json is committed for them.
    for d in dirs:
        if d.name == "sample" or any(m["fixture_id"] == d.name for m in enriched):
            continue
        tracked = {p.name for p in d.iterdir() if p.is_file()}
        assert tracked == {"meta.json"}, f"{d.name} ships more than its meta: {sorted(tracked)}"


def test_the_architecture_diagram_resolves_everywhere_it_points():
    """Two conventions live in one file: the diagrams are relative to `src/ts/` and everything
    else is relative to the repository. The cross-cutting table mixed them, so `cache.py` and
    `clock.py` resolved from nowhere while `evals/` and `scripts/` beside them resolved fine.

    Both are checked here — a node under the diagram root, a backticked path under the repo root
    — because a diagram whose paths do not resolve is a picture, not a map.
    """
    import re

    text = (REPO / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")

    nodes = set(re.findall(r"✔ ([\w/]+\.py|[\w/]+/)", text))
    assert len(nodes) > 10, "the diagram lost its nodes, or the marker changed"
    for node in sorted(nodes):
        assert (REPO / "src/ts" / node).exists(), \
            f"the diagram marks {node} as built and it is not under src/ts/"

    cited = set(re.findall(r"`([A-Za-z0-9_][\w./-]*\.(?:md|py|json|jsonl|csv|svg|toml))`", text))
    cited |= set(re.findall(
        r"`((?:docs|evals|evidence|src|tests|reference|trajectories|scripts|cache)/[\w./-]*)`",
        text))
    missing = sorted(p for p in cited if not (REPO / p.rstrip("/")).exists())
    assert not missing, f"cited from ARCHITECTURE.md and not in the tree: {missing}"


def test_the_reporting_layer_really_does_call_one_model_at_most():
    """`docs/ARCHITECTURE.md` claims the whole reporting pipeline is deterministic "with exactly
    one cosmetic exception". That is the strongest claim in the file — it is why the board, the
    rail and Tier 0 cost nothing — so it is checked rather than trusted."""
    import re

    builders = []
    for path in sorted((REPO / "src/ts/report").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if re.search(r"build_chat_request|\.call\(", source):
            builders.append(path.name)

    assert builders == ["labels.py"], \
        f"the reporting layer builds model requests in {builders}; ARCHITECTURE.md says only labels.py"


def test_the_review_guide_covers_every_gold_case():
    """`make review` is one of the outstanding author actions and README §6 sends a judge here.
    A guide that silently skips a case would leave a label unreviewed while the count says the
    review is done, which is worse than not reviewing at all."""
    import re

    gold = {p.stem for p in (REPO / "evals/gold").glob("*.json")}
    named = set(re.findall(r"c\d{2}_[a-z_]+",
                           (REPO / "evals/REVIEW_ME.md").read_text(encoding="utf-8")))

    assert gold, "no gold labels to review"
    assert gold <= named, f"REVIEW_ME.md never mentions: {sorted(gold - named)}"
    assert not (named - gold), f"REVIEW_ME.md names cases that do not exist: {sorted(named - gold)}"


def test_no_session_logs_ever_ship():
    """Unattended build loops and the fixture farm write raw stdout and stderr into the working
    tree — `.nightlogs/` for the loop that is now gone, `.farmlogs/` for the farm that is not.
    That is raw session output and it belongs nowhere near a public repository. The loop was
    deleted; the guard stays, because the next harness will write logs too."""
    tracked = [p for p in
               __import__("subprocess").run(["git", "ls-files"], cwd=REPO, capture_output=True,
                                            text=True).stdout.splitlines()
               if p.startswith((".nightlogs", ".farmlogs"))]
    assert not tracked, f"session logs are committed: {tracked[:5]}"


def test_the_pseudonymisation_claim_is_the_narrow_one_and_is_counted():
    """`pseudonym()` hashes the author of every message and does not touch message text, which
    carries real `@mentions`. `evals/DATA.md` said `chat.jsonl (pseudonymised)` — wider than the
    truth. The counts are recomputed here rather than quoted, because a limitation stated with a
    number is a disclosure and one stated in general terms is a hedge.
    """
    import json
    import re

    mention = re.compile(r"@([A-Za-z0-9_]{3,25})")
    per_fixture, handles = {}, set()
    for d in sorted((REPO / "evals/fixtures").iterdir()):
        chat = d / "chat.jsonl"
        if not chat.is_file():
            continue
        found = [m for line in chat.read_text(encoding="utf-8").splitlines() if line.strip()
                 for m in mention.findall(json.loads(line).get("text") or "")]
        if found:
            per_fixture[d.name] = len(found)
            handles.update(h.lower() for h in found)

    data = (REPO / "evals/DATA.md").read_text(encoding="utf-8")
    assert "does not touch message **text**" in data, "the limit is no longer stated"
    assert f"**{sum(per_fixture.values())} mentions naming {len(handles)} distinct handles**" in data, \
        (f"DATA.md misstates the exposure; measured {sum(per_fixture.values())} mentions / "
         f"{len(handles)} handles")
    for name, count in per_fixture.items():
        assert f"| `{name}` | {count} |" in data, f"the per-fixture row for {name} is wrong"

    # The reason it is not fixed has to travel with it, or it reads as an oversight.
    assert "content-derived" in data or "derived from" in data
    assert "RISKS.md` #53" in data or "RISKS.md #53" in data


def test_the_frame_captions_carry_no_chat_identity():
    """The overlay these captions describe is the same one that carries real logins in any
    captured frame (RISKS #52). In pixels it leaks; in the derived text it does not, because the
    vision model declines the chat pane — *"The chat is visible but not described."* That is a
    privacy property of what ships, not a stylistic accident, and a re-enrichment with a
    different model could quietly end it.

    Counted from the evaluated fixtures only. `sample` is a hand-written scaffold and including
    it would mean the row count and the character count were drawn from different sets — which is
    exactly the mistake this docstring's own figures were caught making.
    """
    import json
    import re

    mention = re.compile(r"@([A-Za-z0-9_]{3,25})")
    names = re.compile(r"\b(username|usernames|user names?|login|handle|nickname)\b", re.I)
    rows = chars = 0
    for d in sorted((REPO / "evals/fixtures").iterdir()):
        frames = d / "frames.jsonl"
        if d.name == "sample" or not frames.is_file():
            continue
        for line in frames.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            caption = str(json.loads(line).get("caption") or "")
            rows += 1
            chars += len(caption)
            assert not mention.search(caption), f"{d.name}: a caption names a handle"
            assert not names.search(caption), f"{d.name}: a caption transcribes the chat pane"

    data = (REPO / "evals/DATA.md").read_text(encoding="utf-8")
    assert f"{rows} caption" in data and f"{chars:,} characters" in data, \
        f"DATA.md misstates the caption corpus; measured {rows} rows / {chars:,} chars"
