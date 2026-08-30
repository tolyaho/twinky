"""The agent graph on the Method page.

Generated from `workflow/agent.py`, `provenance.py` and the committed trajectories, never drawn
by hand — so a diagram that disagrees with the system is a failing test rather than a picture
nobody re-checked. The plan for this diagram already carried two stale numbers when it was
written (five tools, eight gate codes); there are four tools, and eight codes on the card path
plus two on the abstention path. That is exactly the drift this file exists to prevent.
"""
from pathlib import Path

from ts.report.graph import gate_codes, render, trajectory_counts
from ts.workflow.agent import ALLOWED_TOOLS, MAX_CARDS, MAX_TOOL_CALLS_PER_STEP

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "src/ts/report/static/agent-graph.svg"


def _committed():
    return SVG.read_text(encoding="utf-8")


def test_the_committed_svg_is_what_the_generator_produces_today():
    """`make graph` after any change to the agent, the gate or the trajectories. If this fails,
    the picture on the Method page is describing a system that no longer exists."""
    assert _committed() == render(), "run `make graph` — the diagram is stale"


def test_every_tool_the_agent_allows_is_drawn():
    svg = _committed()

    for tool in ALLOWED_TOOLS:
        assert tool in svg, f"{tool} is allowed by the agent and missing from the diagram"
    assert f"{len(ALLOWED_TOOLS)} bounded tools" in svg


def test_every_gate_check_is_named():
    """A gate whose checks are not named is a claim, not a mechanism."""
    card, abstain = gate_codes(ROOT / "src/ts/provenance.py")
    svg = _committed()

    assert len(card) == 8 and len(abstain) == 2
    for code in card + abstain:
        assert code in svg
    assert f"{len(card)} card checks · {len(abstain)} abstention" in svg


def test_the_controller_bounds_are_the_real_ones():
    svg = _committed()

    assert f"at most {MAX_CARDS}" in svg
    assert f"max {MAX_TOOL_CALLS_PER_STEP} calls per step" in svg


def test_the_edge_counts_are_measured_not_decorative():
    """The whole reason the numbers are on the picture: `get_frame_captions` is the smallest,
    which is the grounding failure in one figure."""
    counts = trajectory_counts(ROOT / "trajectories/product-agent")
    svg = _committed()

    assert counts["runs"] > 0
    assert f"{counts['runs']} recorded runs" in svg
    tools = counts["tools"]
    assert tools["group_repeated"] > tools["get_frame_captions"] * 10
    assert min(tools, key=tools.get) == "get_frame_captions"


def test_missing_trajectories_give_zeros_never_guesses(tmp_path):
    counts = trajectory_counts(tmp_path)

    assert counts == {"runs": 0, "tools": {}, "model_calls": 0, "gate": {}}


def test_the_model_appears_exactly_twice_and_is_drawn_differently():
    """The engineering argument is that the model does as little as possible, so the picture has
    to say it before the caption does."""
    svg = _committed()

    assert svg.count('stroke-dasharray="4 3"') == 3      # two model nodes plus the legend key
    assert "the model — two nodes, and only these two" in svg
    assert "deterministic — checkable, no model" in svg


def test_it_draws_with_no_network_and_no_javascript():
    html = (ROOT / "src/ts/report/static/method.html").read_text(encoding="utf-8")
    svg = _committed()

    assert '<img src="/static/agent-graph.svg"' in html
    # `xmlns="http://www.w3.org/2000/svg"` is a namespace name and `url(#a)` is the arrowhead
    # marker in this same file. Neither fetches. These would.
    for forbidden in ["<script", "@import", "href", "src=", "url(http", "url(//", "@font-face"]:
        assert forbidden not in svg, f"the diagram reaches outside itself via {forbidden}"
    assert svg.count("http") == 1, "the only URI in the file is the SVG namespace"


def test_the_diagram_uses_only_design_md_colours():
    css = (ROOT / "src/ts/report/static/app.css").read_text(encoding="utf-8")
    import re

    in_css = set(re.findall(r"#[0-9a-fA-F]{6}", css))
    in_svg = set(re.findall(r"#[0-9a-fA-F]{6}", _committed()))

    assert in_svg <= in_css, f"colours not in the system: {sorted(in_svg - in_css)}"


def test_the_figure_has_a_real_alt_text():
    html = (ROOT / "src/ts/report/static/method.html").read_text(encoding="utf-8")
    figure = html.split('<figure class="graph">', 1)[1].split("</figure>", 1)[0]

    alt = figure.split('alt="', 1)[1].split('"', 1)[0]
    assert len(alt) > 120, "a diagram carrying the argument needs a description, not a label"
    assert "gate" in alt and "deterministic" in alt
