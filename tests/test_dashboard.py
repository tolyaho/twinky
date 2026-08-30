"""The dashboard: what it is served with, and that it obeys DESIGN.md.

Two of these tests are conformance tests rather than behaviour tests. They exist because the
rules they enforce — no improvised colour, no generated data — are exactly the ones the previous
shell broke, and a rule nobody checks is a rule that comes back.
"""
import json
import re
import shutil
import threading
import urllib.request
from pathlib import Path

import pytest

from ts.report import serve as serve_mod

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "evals" / "fixtures" / "sample"
STATIC = serve_mod.STATIC
REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN = REPO / "DESIGN.md"

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

CARD = {
    "signal_id": "sig_00", "type": "audience_answer", "title": "Chat says лес",
    "distribution": {"лес": 9, "база": 6},
    "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
    "evidence": ["msg_0001", "msg_0002"], "confidence": 0.86,
    "gate": {"ok": True, "violations": []}, "trace_id": "trc_a",
}
BAD_CARD = {
    "signal_id": "sig_01", "type": "warning", "title": "Invented",
    "trigger": {"kind": "speech", "event_id": "tr_0001", "quote": "в лес или на базу?"},
    "evidence": ["msg_does_not_exist"], "confidence": 0.4,
    "gate": {"ok": False, "violations": [{"code": "E_UNKNOWN_MSG", "detail": "not in fixture"}]},
}
RESULT = {
    "system": "agent", "fixture": "fixture", "fixture_id": "sample", "mode": "replay",
    "window_size_ms": 60000, "span_ms": [1756399998000, 1756400022000],
    "counts": {"windows": 1, "verified": 1, "rejected": 1},
    "cache": {"hits": 1, "misses": 0},
    "windows": [{"case_id": "sample_w00", "window_ms": [1756399998000, 1756400022001],
                 "verified": [CARD], "rejected": [BAD_CARD]}],
}


@pytest.fixture
def served(tmp_path):
    shutil.copytree(SAMPLE, tmp_path / "fixture")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "sample.agent.json").write_text(json.dumps(RESULT), encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------- evidence payload
def test_only_cited_events_are_sent_to_the_browser(served):
    events = serve_mod.cited_events(RESULT, served / "fixture")

    # the fixture holds 32 chat messages; the browser gets the three the cards actually name
    assert set(events) == {"msg_0001", "msg_0002", "tr_0001"}
    assert events["msg_0001"]["text"] == "лес"


def test_a_fabricated_citation_is_simply_absent(served):
    """The drawer renders a missing id as "not in the fixture" — the gate made visible."""
    events = serve_mod.cited_events(RESULT, served / "fixture")

    assert "msg_does_not_exist" not in events


def test_an_unknown_trigger_is_not_looked_up(served):
    result = json.loads(json.dumps(RESULT))
    result["windows"][0]["verified"][0]["trigger"] = {"kind": "unknown", "event_id": "unknown"}

    assert "unknown" not in serve_mod.cited_events(result, served / "fixture")


def test_payload_carries_meta_result_and_events(served):
    got = serve_mod.payload(served / "fixture", served / "out")

    assert set(got) == {"meta", "result", "events", "evaluation"}
    assert got["events"]["tr_0001"]["type"] == "transcript_segment"
    # No eval has been run in this fixture, so the editorial section has nothing to show and
    # says so with None rather than an empty table that would read as a measured zero.
    assert got["evaluation"] is None


# --------------------------------------------------------------------------- served end to end
def test_the_dashboard_is_served_over_http(served):
    httpd = serve_mod.make_server(served / "fixture", served / "out", 0, quiet=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        page = urllib.request.urlopen(base + "/").read().decode("utf-8")
        css = urllib.request.urlopen(base + "/static/app.css").read().decode("utf-8")
        api = json.loads(urllib.request.urlopen(base + "/api/replay").read().decode("utf-8"))
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert "Verified audience signals" in page
    assert "not the dashboard" not in page   # the placeholder must be gone now
    assert "--surface-dark" in css
    assert api["result"]["counts"]["verified"] == 1


# --------------------------------------------------------------------------- DESIGN conformance
def _design_tokens():
    block = DESIGN.read_text(encoding="utf-8")
    return {h.lower() for h in HEX.findall(block)}


def test_the_stylesheet_improvises_no_colour():
    used = {h.lower() for h in HEX.findall((STATIC / "app.css").read_text(encoding="utf-8"))}

    assert used <= _design_tokens(), f"not in DESIGN.md: {sorted(used - _design_tokens())}"


def test_display_type_never_exceeds_weight_300():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    display_rules = re.findall(r"\.display[^{]*\{[^}]*\}|\.card h3[^{]*\{[^}]*\}", css)

    assert display_rules
    for rule in display_rules:
        for weight in re.findall(r"font-weight:\s*(\d+)", rule):
            assert int(weight) <= 300, rule


def test_hairlines_not_shadows():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "box-shadow" not in css
    assert css.count("border: 1px solid") >= 3


def test_the_page_fetches_nothing_from_the_network():
    """A judge with no connectivity must still see the real dashboard."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "http://" not in html and "https://" not in html


def test_no_generator_ships_in_the_dashboard():
    """Shipping fake data as real is an integrity-gate failure, and the old shell did it."""
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "Math.random" not in js
    # chat is untrusted data, so it reaches the DOM as text and never as markup
    assert not re.search(r"\.innerHTML\s*=", js)


def test_every_scored_ui_element_is_present():
    """DESIGN.md lists these as scored; a missing one is lost points, not a cosmetic gap."""
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "mode-badge" in html                      # Replay | Live badge
    assert "card.type" in js                         # signal type
    assert "distribution" in js                      # count / share
    assert "conf ${card.confidence}" in js           # confidence
    assert "Not established" in js                   # explicit unknown
    assert "Evidence —" in js                        # evidence drawer
    assert '"rejected"' in js and '"abstained"' in js and '"verified"' in js
    assert "trace ${card.trace_id" in js or "trace " in js
    assert 'id="debug"' in html                      # debug panel for judges


# --------------------------------------------------------------- editorial sections (P4)
def test_the_measured_section_reads_the_eval_rather_than_recomputing_it(served):
    """`evals/scorer.py` owns every published metric. A rate computed a second time in the
    browser would eventually disagree with the one printed in evidence/report.md."""
    (served / "out" / "summary.json").write_text(json.dumps({
        "systems": {"agent": {"cases": 11, "cards": 23, "trigger_accuracy": 0.5,
                              "unmatched_rate": 0.913, "unsupported_rate": 0.739,
                              "signal_recall": 0.182}},
        "fixtures": {}, "reportable": True}), encoding="utf-8")

    got = serve_mod.payload(served / "fixture", served / "out")

    assert got["evaluation"]["systems"]["agent"]["unsupported_rate"] == 0.739


def test_the_dashboard_never_computes_a_rate_itself():
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    # Narrow on purpose: summing a card's own distribution for display is fine. What must not
    # happen is deriving one of the PUBLISHED rates, which evals/scorer.py owns.
    for forbidden in ["unsupported_rate =", "trigger_accuracy =", "signal_recall =",
                      "unmatched_rate =", "/ agg.", "/ result.counts"]:
        assert forbidden not in js, f"the browser is deriving a published metric: {forbidden}"
    assert "evals/scorer.py owns every published metric" in js


def test_the_editorial_sections_stay_hidden_without_an_eval():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="measured" hidden' in html, "an empty table reads as a measured zero"
    assert 'document.getElementById("measured").hidden = false' in js


def test_the_editorial_copy_states_the_result_that_counts_against_the_product():
    """The measured section must not quietly show the agent winning. It loses the headline
    metric and the page has to say so where the table is."""
    html = " ".join((STATIC / "index.html").read_text(encoding="utf-8").split())

    assert "loses restraint" in html
    assert "unsupported-card rate is the worst of the three" in html
    assert "single matched card" in html


def test_the_changelog_section_names_the_removed_experiment_and_the_failure_mode():
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "removed experiment" in html
    assert "zero additional" in html.lower()
    assert "get_frame_captions" in html
    assert "largest contributor" in html


# --------------------------------------------------------------- type scale (block C)
def _css():
    return (STATIC / "app.css").read_text(encoding="utf-8")


def test_the_hero_uses_the_display_mega_row():
    """DESIGN.md's display scale is identical to the fetched ElevenLabs reference, and its
    homepage-hero row is 64px / 300 / 1.05 / -1.92px. The hero was rendering at the 48px
    display-xl row, which is most of why the page read as a tool rather than an editorial
    surface."""
    css = _css()
    block = css.split(".hero-title {", 1)[1].split("}", 1)[0]

    assert "font-size: 64px" in block
    assert "letter-spacing: -1.92px" in block
    assert "line-height: 1.05" in block


def test_uppercase_labels_use_the_scale_not_an_improvised_value():
    """caption-uppercase is 12px / 600 / 1.4 / +0.96px. Two labels added for the editorial
    sections had improvised 0.8px tracking and no weight, so they did not match the badges
    already on the page."""
    css = _css()

    assert "letter-spacing: .8px" not in css, "an improvised tracking value is back"
    for block in css.split("text-transform: uppercase")[:-1]:
        tail = block.rsplit("{", 1)[-1]
        assert "letter-spacing: .96px" in tail, f"uppercase label off-scale: {tail.strip()[:80]}"


def test_body_keeps_the_positive_editorial_tracking():
    """+0.16px on body is what makes it read editorial rather than SaaS. DESIGN.md says not to
    skip it, and it is the cheapest part of the whole look."""
    assert "letter-spacing: .16px" in _css()


def test_display_type_is_never_heavier_than_300_anywhere():
    css = _css()
    for block in css.split(".display")[1:]:
        body = block.split("}", 1)[0]
        for weight in ("400", "500", "600", "700", "bold"):
            assert f"font-weight: {weight}" not in body


def test_every_hex_still_comes_from_the_design_tokens():
    """Re-asserted here because the type pass touched the stylesheet: the reference and
    DESIGN.md agree on all 19 colour tokens, and app.css may use only those."""
    import re

    design = (REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8")
    allowed = {m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}", design)}
    used = {m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}", _css())}

    assert used <= allowed, f"improvised colour: {sorted(used - allowed)}"
