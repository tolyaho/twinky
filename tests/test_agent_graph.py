"""The agent graph on the Method page.

Generated from `workflow/agent.py`, `provenance.py` and the committed trajectories, never drawn
by hand — so a diagram that disagrees with the system is a failing test rather than a picture
nobody re-checked. The plan for this diagram already carried two stale numbers when it was
written (five tools, eight gate codes); there are four tools, and eight codes on the card path
plus two on the abstention path. That is exactly the drift this file exists to prevent.
"""
import json
from pathlib import Path

from ts.report.graph import HEIGHT, WIDTH, gate_codes, render, trajectory_counts
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

    assert counts == {"runs": 0, "tool_runs": 0, "tools": {}, "steps_used": {}, "budget": 0,
                      "model_calls": 0, "gate": {}}


def test_tool_counts_are_divided_by_the_runs_that_could_call_a_tool():
    """The picture said `118 runs` beside `get_frame_captions 2` while 59 of those runs were
    baselines with no tools at all. Half the denominator was runs that could not have called
    anything, which flatters the agent on a number the whole diagram exists to indict."""
    counts = trajectory_counts(ROOT / "trajectories/product-agent")
    svg = _committed()

    assert 0 < counts["tool_runs"] < counts["runs"], "baselines have no tools; they cannot count"
    assert f'{counts["tool_runs"]} runs with tools' in svg
    assert f'{counts["runs"]} runs with tools' not in svg


def test_the_diagram_says_the_agent_looks_once():
    """The totals alone read as coverage. The distribution is the finding: a four-step budget,
    one step spent, and never on the modality that could explain the chat."""
    counts = trajectory_counts(ROOT / "trajectories/product-agent")
    svg = _committed()

    single, budget = counts["steps_used"].get(1, 0), counts["budget"]
    assert budget == 4 and single > counts["tool_runs"] * 0.8
    assert f'{single} of {counts["tool_runs"]} runs spent 1 of their {budget} steps' in svg
    assert "and the one step was chat" in svg
    assert counts["steps_used"].get(budget, 0) == 0, "no run ever used its whole budget"

    # "on chat" is a claim about the trajectories, so hold it to them rather than to the caption.
    chat_tools = {"group_repeated", "get_chat_window"}
    for path in sorted((ROOT / "trajectories/product-agent").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if (doc.get("meta") or {}).get("max_steps") is None:
            continue
        calls = [s["tool"] for s in doc["steps"] if s.get("kind") == "tool_call"]
        if len(calls) == 1:
            assert calls[0] in chat_tools, f"{path.name} spent its one step on {calls[0]}"


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


def test_the_img_reserves_the_space_the_svg_actually_needs():
    """The attribute said 470 against a 412 canvas. CSS `height: auto` hid the stretch, so the
    only symptom was the browser reserving a box 14% too tall and the page jumping when the
    diagram arrived — on the page the whole engineering argument lives on."""
    html = (ROOT / "src/ts/report/static/method.html").read_text(encoding="utf-8")
    svg = _committed()

    assert f'width="{WIDTH}" height="{HEIGHT}"' in html
    assert f'viewBox="0 0 {WIDTH} {HEIGHT}"' in svg


def test_the_shot_list_points_at_numbers_that_are_on_the_diagram():
    """Shot 9 tells the author to point at specific figures. If the trajectories grow and the
    diagram moves, the narration has to move with it — otherwise the video says one number while
    the screen shows another, which is the one mistake a recording cannot walk back."""
    shots = (ROOT / "video/SHOTLIST.md").read_text(encoding="utf-8")
    counts = trajectory_counts(ROOT / "trajectories/product-agent")
    svg = _committed()

    quoted = [line.strip(" *`") for line in shots.split("Point at `get_frame_captions", 1)[1]
              .split("**Say:**", 1)[0].split("\n")]
    for fragment in [f'{counts["steps_used"][1]} of {counts["tool_runs"]} runs',
                     "and the one step was chat"]:
        assert any(fragment in q for q in quoted), f"shot 9 no longer quotes {fragment!r}"
        assert fragment in svg, f"shot 9 quotes {fragment!r} and the diagram does not say it"


def test_the_figure_has_a_real_alt_text():
    html = (ROOT / "src/ts/report/static/method.html").read_text(encoding="utf-8")
    figure = html.split('<figure class="graph">', 1)[1].split("</figure>", 1)[0]

    alt = figure.split('alt="', 1)[1].split('"', 1)[0]
    assert len(alt) > 120, "a diagram carrying the argument needs a description, not a label"
    assert "gate" in alt and "deterministic" in alt
