"""The agent graph on the Method page.

Generated from `workflow/agent.py`, `provenance.py` and the committed trajectories, never drawn
by hand — so a diagram that disagrees with the system is a failing test rather than a picture
nobody re-checked. The plan for this diagram already carried two stale numbers when it was
written (five tools, eight gate codes); there are four tools, and eight codes on the card path
plus two on the abstention path. That is exactly the drift this file exists to prevent.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ts.report.graph import HEIGHT, WIDTH, gate_codes, render, text_width, trajectory_counts
from ts.workflow.agent import ALLOWED_TOOLS, MAX_CARDS, MAX_TOOL_CALLS_PER_STEP

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "src/ts/report/static/agent-graph.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"

# What counts as too close. Nothing may overlap, and a label inside a node keeps a real gutter
# rather than kissing the border it sits in.
CLEARANCE = 6
NODE_PADDING = 10


def _committed():
    return SVG.read_text(encoding="utf-8")


def _boxes():
    """Every drawn thing as a rectangle in canvas coordinates.

    Text is measured with `text_width`, which over-estimates on purpose — see its docstring. A
    label's box runs from its baseline up by the font size and down by a quarter of it for the
    descenders, which is close enough for a collision test and does not need a browser.
    """
    root = ET.fromstring(_committed())
    rects, texts = [], []
    for el in root.iter():
        if el.tag == f"{SVG_NS}rect":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, h = float(el.get("width")), float(el.get("height"))
            if w >= WIDTH and h >= HEIGHT:
                continue                                   # the canvas itself, not a node
            rects.append((x, y, w, h, ""))
        elif el.tag == f"{SVG_NS}text":
            label = "".join(el.itertext())
            size = float(el.get("font-size"))
            mono = "mono" in (el.get("font-family") or "")
            w = text_width(label, size, mono=mono)
            x, y = float(el.get("x")), float(el.get("y"))
            anchor = el.get("text-anchor", "start")
            x = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
            texts.append((x, y - size, w, size * 1.25, label))
    return rects, texts


def _hgap(a, b):
    return max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]))


def _vgap(a, b):
    return max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]))


def _too_close(a, b):
    """Why this is not one distance: two labels stacked as lines of a paragraph sit a couple of
    pixels apart by design, and that is leading, not a collision. Only things sharing a
    horizontal band are competing for the same room, and those need a real gutter."""
    if _vgap(a, b) >= 0:
        return None                                        # different bands; leading is fine
    gap = _hgap(a, b)
    return gap if gap < CLEARANCE else None


def _contains(outer, inner):
    ox, oy, ow, oh, _ = outer
    ix, iy, iw, ih, _ = inner
    return ox <= ix and oy <= iy and ix + iw <= ox + ow and iy + ih <= oy + oh


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


def test_nothing_in_the_diagram_is_drawn_on_top_of_anything_else():
    """The diagram shipped for weeks with the provenance gate sitting across the tool caption and
    the run count, and the legend's second key printed over the end of the first. Every check
    here reads the numbers rather than the picture, so none of them saw it — the argument was
    correct and unreadable at the same time.

    The gaps were not wrong by much. The legend cleared the next swatch by 1.4 px in Chromium and
    overlapped it on the author's machine, because the file names a font it cannot ship and gets
    whatever the browser has. So this measures against a width that assumes the wider face.
    """
    rects, texts = _boxes()
    collisions = []

    for label in texts:
        for node in rects:
            if _contains(node, label):
                continue
            gap = _too_close(label, node)
            if gap is not None:
                collisions.append(f"{label[4]!r} sits {gap:.1f}px from the box at "
                                  f"x={node[0]:.0f} y={node[1]:.0f}")
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            gap = _too_close(a, b)
            if gap is not None:
                collisions.append(f"{a[4]!r} sits {gap:.1f}px from {b[4]!r}")

    assert not collisions, "\n".join(collisions)


def test_every_label_fits_the_node_it_is_printed_in():
    """A subtitle wider than its own box is the same defect one step earlier: it does not look
    broken until the fallback font is 10% wider, and then it hangs out of the border."""
    rects, texts = _boxes()
    overflows = []

    for label in texts:
        holders = [r for r in rects if r[1] <= label[1] and label[1] + label[3] <= r[1] + r[3]
                   and r[0] <= label[0] < r[0] + r[2]]
        for node in holders:
            room = node[0] + node[2] - NODE_PADDING - (label[0] + label[2])
            if room < 0:
                overflows.append(f"{label[4]!r} overruns its box by {-room:.0f}px")

    assert not overflows, "\n".join(overflows)


def test_the_canvas_is_tall_enough_for_everything_drawn_on_it():
    rects, texts = _boxes()
    lowest = max(b[1] + b[3] for b in rects + texts)
    widest = max(b[0] + b[2] for b in rects + texts)

    assert lowest <= HEIGHT - 8, f"the diagram runs {lowest - HEIGHT:.0f}px past the canvas"
    assert widest <= WIDTH - 8, f"the diagram runs {widest - WIDTH:.0f}px past the canvas"
    # Slack, not a fixed size: the point is that the canvas is fitted, not that it is 448 tall.
    assert HEIGHT - lowest < 40, "the canvas has a band of dead space at the bottom"


def test_the_figure_has_a_real_alt_text():
    html = (ROOT / "src/ts/report/static/method.html").read_text(encoding="utf-8")
    figure = html.split('<figure class="graph">', 1)[1].split("</figure>", 1)[0]

    alt = figure.split('alt="', 1)[1].split('"', 1)[0]
    assert len(alt) > 120, "a diagram carrying the argument needs a description, not a label"
    assert "gate" in alt and "deterministic" in alt
