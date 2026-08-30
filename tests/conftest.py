import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True, scope="session")
def _traces_stay_out_of_the_deliverable(tmp_path_factory):
    """`trajectories/` is a graded deliverable: it must hold real runs and nothing else.

    Tests that construct an agent without changing directory wrote there — 55 files with case
    ids no evaluation case has. Redirecting for the whole session fixes the class of problem
    rather than the instances of it.
    """
    import os

    previous = os.environ.get("TS_TRACE_DIR")
    os.environ["TS_TRACE_DIR"] = str(tmp_path_factory.mktemp("trajectories"))
    yield
    if previous is None:
        os.environ.pop("TS_TRACE_DIR", None)
    else:
        os.environ["TS_TRACE_DIR"] = previous
