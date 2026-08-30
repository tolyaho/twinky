"""The agent graph, generated from the code it describes.

Hand-drawing this would have been faster and it would have been wrong within a day. Every label,
bound and count below is read from `workflow/agent.py`, `provenance.py` and the committed
trajectories, so a diagram that disagrees with the system is a failing test rather than a
picture nobody re-checked. The two numbers in the plan for this diagram were already stale when
it was written — it says five tools and eight gate codes; there are four tools, and eight codes
on the card path plus two more on the abstention path.

The argument the picture has to make before the caption does: **the model does as little as
possible.** Everything checkable is deterministic. So deterministic nodes are solid and filled,
the two model nodes are dashed and empty, and the edge counts are real call counts from 118
recorded runs — including the one that matters most, `get_frame_captions` at 2, which is the
measured form of the grounding failure.

No library, no webfont, no network: an `<svg>` a browser draws from bytes already on disk.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..workflow.agent import ALLOWED_TOOLS, MAX_CARDS, MAX_TOOL_CALLS_PER_STEP

# From DESIGN.md, the same tokens app.css uses. Baked in rather than inherited because this is
# served as an image and an image cannot read the page's stylesheet.
INK = "#0c0a09"
BODY = "#4e4e4e"
MUTED = "#777169"
MUTED_SOFT = "#a8a29e"
HAIRLINE = "#d6d3d1"
SURFACE = "#ffffff"
CANVAS_SOFT = "#fafafa"

TRAJECTORIES = Path("trajectories/product-agent")


def gate_codes(source: Path | str = Path("src/ts/provenance.py")) -> Tuple[List[str], List[str]]:
    """The card checks and the abstention checks, read out of the gate itself."""
    text = Path(source).read_text(encoding="utf-8")

    def codes_in(function: str) -> List[str]:
        body = text.split(f"def {function}", 1)[1].split("\ndef ", 1)[0]
        return sorted(set(re.findall(r'"(E_[A-Z_]+)"', body)))

    return codes_in("check_card"), codes_in("check_abstention")


def trajectory_counts(root: Path | str = TRAJECTORIES) -> Dict[str, Any]:
    """Real call counts from the recorded runs. Absent trajectories give zeros, never guesses."""
    root = Path(root)
    tools: Counter = Counter()
    gate: Counter = Counter()
    model_calls = 0
    runs = 0
    for path in sorted(root.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        runs += 1
        for step in doc.get("steps") or []:
            kind = step.get("kind") or step.get("type")
            if kind == "tool_call":
                tools[step.get("tool") or step.get("name")] += 1
            elif kind == "model_call":
                model_calls += 1
            elif kind == "provenance_gate":
                gate["verified" if step.get("ok") else "rejected"] += 1
    return {"runs": runs, "tools": dict(tools), "model_calls": model_calls, "gate": dict(gate)}


def _box(x: int, y: int, w: int, h: int, title: str, sub: str, *, model: bool) -> str:
    """A node. Model nodes are dashed and empty; deterministic nodes are solid and filled."""
    stroke = MUTED if model else INK
    dash = ' stroke-dasharray="4 3"' if model else ""
    fill = "none" if model else CANVAS_SOFT
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1"{dash}/>'
        f'<text x="{x + 14}" y="{y + 25}" font-size="13" font-weight="500" fill="{INK}">'
        f'{title}</text>'
        f'<text x="{x + 14}" y="{y + 44}" font-size="11" fill="{MUTED}">{sub}</text>'
    )


def _arrow(x1: int, y1: int, x2: int, y2: int, label: str = "") -> str:
    mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
    text = (f'<text x="{mid_x}" y="{mid_y - 6}" font-size="10" fill="{MUTED_SOFT}" '
            f'text-anchor="middle">{label}</text>') if label else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{HAIRLINE}" '
            f'stroke-width="1" marker-end="url(#a)"/>{text}')


def render(*, trajectories: Path | str = TRAJECTORIES,
           provenance: Path | str = Path("src/ts/provenance.py")) -> str:
    """The whole diagram as an SVG string, built from the running system's own numbers."""
    card_codes, abstain_codes = gate_codes(provenance)
    counts = trajectory_counts(trajectories)
    tools = sorted(ALLOWED_TOOLS)
    calls = counts["tools"]

    parts: List[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 412" width="980" height="412" '
        'font-family="Inter, system-ui, sans-serif" role="img" '
        'aria-label="How one window becomes a verified or rejected card">',
        f'<defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" '
        f'markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="{HAIRLINE}"/>'
        f'</marker></defs>',
        f'<rect width="980" height="412" fill="{SURFACE}"/>',
    ]

    # legend — the argument, stated once, at the top
    parts += [
        f'<rect x="24" y="18" width="14" height="14" rx="3" fill="{CANVAS_SOFT}" '
        f'stroke="{INK}"/>',
        f'<text x="46" y="30" font-size="11" fill="{BODY}">deterministic — checkable, '
        f'no model</text>',
        f'<rect x="240" y="18" width="14" height="14" rx="3" fill="none" stroke="{MUTED}" '
        f'stroke-dasharray="4 3"/>',
        f'<text x="262" y="30" font-size="11" fill="{BODY}">the model — two nodes, and only '
        f'these two</text>',
        f'<text x="612" y="30" font-size="11" fill="{MUTED_SOFT}">edge counts are real: '
        f'{counts["runs"]} recorded runs</text>',
    ]

    parts.append(_box(24, 60, 170, 62, "sources", "chat · speech · frames", model=False))
    parts.append(_arrow(194, 91, 244, 91))
    parts.append(_box(244, 60, 170, 62, "reduce", "canonical, counted, ids kept", model=False))
    parts.append(_arrow(414, 91, 464, 91))

    parts.append(_box(464, 48, 210, 86, "the model",
                      f"picks tools or answers · t=0", model=True))
    parts.append(_arrow(674, 91, 724, 91, "answer"))

    # the tool row, with real call counts
    parts.append(f'<text x="464" y="168" font-size="11" fill="{MUTED}">'
                 f'{len(tools)} bounded tools · max {MAX_TOOL_CALLS_PER_STEP} calls per step, '
                 f'executed and validated by the controller</text>')
    for i, tool in enumerate(tools):
        y = 180 + i * 34
        n = calls.get(tool, 0)
        emphasis = INK if n else MUTED_SOFT
        parts.append(
            f'<rect x="464" y="{y}" width="210" height="26" rx="6" fill="{SURFACE}" '
            f'stroke="{HAIRLINE}"/>'
            f'<text x="476" y="{y + 17}" font-size="11" fill="{BODY}">{tool}</text>'
            f'<text x="662" y="{y + 17}" font-size="11" fill="{emphasis}" '
            f'text-anchor="end">{n}</text>')
    parts.append(_arrow(569, 134, 569, 176, ""))
    parts.append(f'<text x="700" y="196" font-size="10" fill="{MUTED_SOFT}">calls, across</text>'
                 f'<text x="700" y="210" font-size="10" fill="{MUTED_SOFT}">'
                 f'{counts["runs"]} runs</text>')

    parts.append(_box(724, 60, 232, 62, "card JSON",
                      f"at most {MAX_CARDS}, capped by the controller", model=True))
    parts.append(_arrow(840, 122, 840, 168))

    parts.append(_box(724, 168, 232, 76, "provenance gate",
                      f"{len(card_codes)} card checks · {len(abstain_codes)} abstention",
                      model=False))
    parts.append(_arrow(840, 244, 840, 288))

    verified = counts["gate"].get("verified", 0)
    rejected = counts["gate"].get("rejected", 0)
    parts.append(_box(724, 288, 110, 56, "verified", f"{verified}", model=False))
    parts.append(_box(846, 288, 110, 56, "rejected", f"{rejected}", model=False))

    # the codes, listed — a gate whose checks are not named is a claim, not a mechanism
    parts.append(f'<text x="24" y="172" font-size="11" fill="{MUTED}">'
                 f'every check the gate makes:</text>')
    for i, code in enumerate(card_codes + abstain_codes):
        col, row = divmod(i, 5)
        parts.append(f'<text x="{24 + col * 210}" y="{194 + row * 18}" font-size="10.5" '
                     f'fill="{BODY if i < len(card_codes) else MUTED_SOFT}" '
                     f'font-family="ui-monospace, monospace">{code}</text>')

    parts.append(f'<text x="24" y="384" font-size="11" fill="{MUTED}">'
                 f'The model chooses and writes. Everything that can be checked is checked '
                 f'without it — and a card that fails any check is thrown away.</text>')
    parts.append("</svg>")
    return "".join(parts)


def write(target: Path | str = Path("src/ts/report/static/agent-graph.svg"), **kwargs) -> Path:
    path = Path(target)
    path.write_text(render(**kwargs), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write())
