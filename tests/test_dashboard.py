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

# The front page is the product (live playback); the evidence story lives at /method. Tests that
# guard the evidence copy read the method page, tests that guard the playback read the live one.
LIVE_HTML = STATIC / "index.html"
LIVE_JS = STATIC / "live.js"
METHOD_HTML = STATIC / "method.html"
METHOD_JS = STATIC / "method.js"
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

    assert set(got) == {"meta", "result", "events", "evaluation", "hero"}
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

    assert "Live chat" in page and "Grounded signals" in page
    assert "not the dashboard" not in page   # the placeholder must be gone now
    assert "--surface-dark" in css
    assert api["result"]["counts"]["verified"] == 1


# --------------------------------------------------------------------------- DESIGN conformance
def _design_tokens():
    block = DESIGN.read_text(encoding="utf-8")
    return {h.lower() for h in HEX.findall(block)}


def test_the_stylesheet_improvises_no_colour():
    # Comments may name a colour they forbid; only declarations count. Third time this guard has
    # tripped on its own documentation, so it now reads code the way the other two do.
    css = re.sub(r"/\*.*?\*/", " ", (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)
    used = {h.lower() for h in HEX.findall(css)}

    assert used <= _design_tokens(), f"not in DESIGN.md: {sorted(used - _design_tokens())}"


def test_display_type_never_exceeds_weight_300():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    display_rules = re.findall(r"\.display[^{]*\{[^}]*\}|\.card h3[^{]*\{[^}]*\}", css)

    assert display_rules
    for rule in display_rules:
        for weight in re.findall(r"font-weight:\s*(\d+)", rule):
            assert int(weight) <= 300, rule


def test_hairlines_not_shadows():
    """DESIGN.md defines exactly one shadow tier — `--shadow-hover`, "the ONLY shadow tier" —
    and puts it on hovered cards. This used to forbid `box-shadow` outright, which was stricter
    than the design it enforces. Tightened rather than relaxed: the value must be the token, the
    token must be the documented one, and it may only appear on a hover state."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    # the stylesheet's tier must be the one DESIGN.md documents, whitespace aside
    norm = lambda s: re.sub(r"\s+", "", s)
    design = (REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8")
    documented = re.search(r"--shadow-hover:\s*([^;]+);", design)
    declared = re.search(r"--shadow-hover:\s*([^;]+);", css)
    assert documented and declared, "the shadow tier is not declared in both files"
    assert norm(declared.group(1)) == norm(documented.group(1)), (
        f"stylesheet tier {declared.group(1)!r} != DESIGN.md {documented.group(1)!r}")

    declarations = re.findall(r"box-shadow:\s*([^;]+);", css)
    assert declarations, "the one hover tier should be in use"
    for value in declarations:
        assert value.strip() == "var(--shadow-hover)", f"improvised shadow: {value.strip()}"

    # ...and only ever on hover.
    for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "box-shadow:" in rule[1] and "--shadow-hover" not in rule[0]:
            assert ":hover" in rule[0], f"shadow off a hover state: {rule[0].strip()[:70]}"

    # hairlines remain the structural device
    assert css.count("border: 1px solid") >= 8


def test_only_one_shadow_tier_is_defined():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    tiers = re.findall(r"--shadow[a-z-]*:", css)

    assert len(tiers) == 1, f"the system allows one shadow tier, found {tiers}"


def test_the_page_fetches_nothing_from_the_network():
    """A judge with no connectivity must still see the real dashboard."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "http://" not in html and "https://" not in html


def test_no_generator_ships_in_the_dashboard():
    """Shipping fake data as real is an integrity-gate failure, and the old shell did it."""
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert "Math.random" not in js
    # chat is untrusted data, so it reaches the DOM as text and never as markup
    assert not re.search(r"\.innerHTML\s*=", js)


def test_every_scored_ui_element_is_present():
    """DESIGN.md lists these as scored; a missing one is lost points, not a cosmetic gap."""
    js = (METHOD_JS).read_text(encoding="utf-8")
    html = (METHOD_HTML).read_text(encoding="utf-8")

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
    js = (METHOD_JS).read_text(encoding="utf-8")

    # Narrow on purpose: summing a card's own distribution for display is fine. What must not
    # happen is deriving one of the PUBLISHED rates, which evals/scorer.py owns.
    for forbidden in ["unsupported_rate =", "trigger_accuracy =", "signal_recall =",
                      "unmatched_rate =", "/ agg.", "/ result.counts"]:
        assert forbidden not in js, f"the browser is deriving a published metric: {forbidden}"
    assert "evals/scorer.py owns every published metric" in js


def test_the_editorial_sections_stay_hidden_without_an_eval():
    html = (METHOD_HTML).read_text(encoding="utf-8")
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert 'id="measured" hidden' in html, "an empty table reads as a measured zero"
    assert 'document.getElementById("measured").hidden = false' in js


def test_the_editorial_copy_states_the_result_that_counts_against_the_product():
    """The measured section must not quietly show the agent winning. It loses the headline
    metric and the page has to say so where the table is."""
    html = " ".join((METHOD_HTML).read_text(encoding="utf-8").split())

    assert "loses restraint" in html
    assert "unsupported-card rate is the worst of the three" in html
    assert "single matched card" in html


def test_the_changelog_section_names_the_removed_experiment_and_the_failure_mode():
    html = (METHOD_HTML).read_text(encoding="utf-8")

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


# --------------------------------------------------------------- the visual pass
def test_signal_status_is_never_conveyed_by_colour():
    """A product decision, not a style one. verified / abstained / rejected are carried by label,
    weight and hairline. Colour-coding a status invites the reader to skim it instead of opening
    the evidence, which is the one thing this product asks them to do."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    for state in (".pill.verified", ".pill.abstained", ".pill.rejected"):
        block = css.split(state, 1)[1].split("}", 1)[0]
        for chromatic in ("--success", "--error", "--orb-"):
            assert chromatic not in block, f"{state} is colour-coded via {chromatic}"


def test_the_orbs_are_atmosphere_and_nothing_else():
    """Pastel orbs are weather: soft, blurred, low opacity, behind content, meaningless. Never a
    fill behind text, never a text colour, never a state or chart colour."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    orb = css.split(".orb {", 1)[1].split("}", 1)[0]

    assert "z-index: -1" in orb, "orbs must sit behind content"
    assert "blur(" in orb
    assert "pointer-events: none" in orb
    opacity = float(re.search(r"opacity:\s*([\d.]+)", orb).group(1))
    assert 0.25 <= opacity <= 0.45, f"orb opacity {opacity} is outside atmosphere range"

    # the orb tokens may only be used by the orbs themselves
    for block in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "--orb-" in block[1] and "--orb-mint:" not in block[1]:
            assert ".orb" in block[0], f"orb colour used outside atmosphere: {block[0].strip()[:60]}"


def test_the_stage_plays_real_data_or_nothing():
    """The hero is the product's argument. If the run verified no card there is no argument to
    make, so it must stay hidden rather than animate a claim the system never produced."""
    js = (METHOD_JS).read_text(encoding="utf-8")
    html = (METHOD_HTML).read_text(encoding="utf-8")

    assert 'id="stage" hidden' in html
    assert "if (!hero || !hero.card" in js, "no grounded card means no stage"
    assert "Math.random" not in js
    # every string it shows comes from the payload
    assert "hero.stream" in js and "card.title" in js


def test_the_stage_is_deterministic_so_it_can_be_filmed():
    """Two plays must be identical: the video opens on this shot, and a jittering hero cannot be
    cut against a voiceover."""
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert "Math.random" not in js
    assert "STAGE_STEP_MS" in js, "timing must be a named constant, not improvised"
    assert "stageStop" in js, "the loop has to be stoppable"


def test_reduced_motion_is_respected():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "prefers-reduced-motion" in css


def test_nothing_scrolls_horizontally():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "overflow-x: hidden" in css, "the orbs extend past the viewport by design"
    assert "max-width: var(--measure)" in css


# --------------------------------------------------------------- accessibility + glass
def test_focus_is_restyled_never_removed():
    """HIGH severity in the UX guidance, and absent entirely before this pass: every operable
    control needs a visible focus indicator. Removing the outline without a replacement is the
    named anti-pattern."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert ":focus-visible" in css
    block = css.split(":focus-visible", 1)[1].split("}", 1)[0]
    assert "outline:" in block and "none" not in block.split("outline:")[1].split(";")[0]
    assert "outline-offset" in block
    # nothing may strip the indicator elsewhere
    assert "outline: none" not in css and "outline:none" not in css


def test_clickable_things_say_so():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert re.search(r"button,\s*summary,\s*a\s*\{[^}]*cursor:\s*pointer", css)


def test_glass_is_translucent_white_not_a_new_colour():
    """Frosted surfaces carry no hue of their own, so the palette is unchanged and text keeps
    the contrast it already had against the canvas."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    design = (REPO_ROOT / "DESIGN.md").read_text(encoding="utf-8")

    for token in ("--glass-bg", "--glass-border", "--glass-blur"):
        assert token in css and token in design, f"{token} must exist in both"

    blur = int(re.search(r"--glass-blur:\s*(\d+)px", css).group(1))
    assert 10 <= blur <= 20, f"blur {blur}px is outside the frosted-glass band"
    assert "-webkit-backdrop-filter" in css, "Safari needs the prefixed property"


def test_the_glass_is_only_on_surfaces_that_overlap_content():
    """Glass everywhere is a gimmick. It belongs on the sticky bar and the stage header — the
    two things that sit over scrolling content."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    users = [sel.strip() for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
             if "backdrop-filter" in body and "--glass-blur:" not in body]

    assert users, "the glass tokens are defined but unused"
    for selector in users:
        assert ".bar" in selector or ".stage-head" in selector, f"glass on {selector}"


def test_the_sections_carry_the_story_in_order():
    """The page is an argument: what the audience said, what did not survive, whether it is
    actually better, how it got here. The eyebrows make that order legible."""
    html = (METHOD_HTML).read_text(encoding="utf-8")
    order = re.findall(r'class="eyebrow">(\d+) — ([^<]+)<', html)

    assert [n for n, _ in order] == ["01", "02", "03", "04"], f"story order broken: {order}"


# --------------------------------------------------------------- the hero, pinned and grounded
def test_the_hero_shows_one_grounded_card_not_three_echoes():
    """The hero used to render three cards reading "Chat mention of X" under the line
    "caused by unknown unknown" — echoes, under a headline about causation. A card that cannot
    name its cause cannot carry this argument."""
    assert serve_mod._grounded({
        "gate": {"ok": True}, "type": "reaction", "evidence": ["m1"],
        "trigger": {"event_id": "frm_1", "quote": "librarian", "kind": "screen"}})

    for bad in (
        {"gate": {"ok": False}, "type": "reaction", "evidence": ["m"], "trigger": {"event_id": "f", "quote": "q"}},
        {"gate": {"ok": True}, "type": "none", "evidence": ["m"], "trigger": {"event_id": "f", "quote": "q"}},
        {"gate": {"ok": True}, "type": "reaction", "evidence": ["m"], "trigger": {"event_id": "unknown", "quote": "q"}},
        {"gate": {"ok": True}, "type": "reaction", "evidence": ["m"], "trigger": {"event_id": "f"}},
        {"gate": {"ok": True}, "type": "reaction", "evidence": [], "trigger": {"event_id": "f", "quote": "q"}},
    ):
        assert not serve_mod._grounded(bad), bad


def test_the_words_unknown_unknown_appear_nowhere():
    """The exact string a reader saw on the page. Checked against what can reach the DOM —
    comments are allowed to name the bug they fixed, and one does."""
    for name in ("live.js", "method.js", "index.html", "method.html", "app.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        code = re.sub(r"^\s*//.*$", " ", code, flags=re.M)
        code = re.sub(r"<!--.*?-->", " ", code, flags=re.S)
        assert "unknown unknown" not in code.lower(), name


def test_a_chart_never_renders_with_fewer_than_two_buckets():
    """One bucket produced a column of indices, empty grey bars and a vertical one-character
    label down the right edge. A chart with nothing to compare is worse than no chart."""
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert "MIN_CHART_BUCKETS = 2" in js
    assert "entries.length < MIN_CHART_BUCKETS" in js
    assert "distinct === 1" in js, "all-equal buckets carry no information either"
    assert "dist-flat" in js, "the fallback must still state the fact as text"


def test_the_hero_names_the_system_that_produced_the_card():
    """The pinned card comes from the single-prompt baseline on that window, not the agent.
    Showing it unlabelled under the product's own headline would be a quiet misrepresentation."""
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert "single-prompt baseline" in js
    assert "hero.system" in js


def test_no_heading_claims_verification_over_an_abstention():
    """Section 01 was headed "Verified audience signals" while every card under it was badged
    ABSTAINED with "Not established." A heading may not claim what its contents deny."""
    html = (METHOD_HTML).read_text(encoding="utf-8")
    js = (METHOD_JS).read_text(encoding="utf-8")

    assert "Verified audience signals" not in html
    # the three outcomes are now one section with three states, each labelled for what it holds
    assert 'data-seg="grounded"' in html and 'data-seg="abstained"' in html
    assert 'data-seg="rejected"' in html
    assert 'isGrounded(card) ? "grounded" : "abstained"' in js


def test_abstentions_are_framed_as_correct_behaviour_not_failure():
    js = " ".join((METHOD_JS).read_text(encoding="utf-8").split())

    assert "could not tie to any moment" in js
    assert "instead of " + '"' + " naming a plausible one" not in js  # phrasing, not a claim
    assert "naming a plausible one" in js


# --------------------------------------------------------------- brand
def test_the_wordmark_is_a_mark_not_body_text():
    """"Twitch Agent" set in the body face is not a wordmark. The glyph means what the product
    means: a filled dot bound by a hairline to an outlined dot — signal bound to its cause."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "mark-glyph" in html and "<svg" in html
    assert html.count("<circle") >= 2 and "<line" in html
    block = css.split(".mark-name", 1)[1].split("}", 1)[0]
    assert "font-weight: 300" in block, "the wordmark is display type, never heavier"
    assert "letter-spacing: -" in block, "display tracking is negative"


def test_the_favicon_is_the_same_mark():
    svg = (STATIC / "favicon.svg").read_text(encoding="utf-8")

    assert svg.count("<circle") == 2 and "<line" in svg
    assert "#0c0a09" in svg and "#f5f5f5" in svg, "favicon uses the ink and canvas tokens"


def test_svg_is_served_with_the_right_content_type():
    assert '".svg": "image/svg+xml"' in (
        (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8"))


def test_the_name_is_treated_identically_everywhere():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "<title>Twitch Agent" in html
    assert readme.startswith("# Twitch Agent")
    assert "Twitch&nbsp;Agent" in html or "Twitch Agent" in html


# --------------------------------------------------------------- cards as objects
def test_the_trigger_quote_is_the_emphasis_not_the_type_label():
    """The quote is the most important text on a card — it is the cause, verbatim. The type
    badge was competing with it by carrying a filled background."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    quote = css.split(".quote {", 1)[1].split("}", 1)[0]
    assert "font-size: 18px" in quote and "font-style: italic" in quote
    assert "border-left: 2px solid var(--hairline-strong)" in quote

    pill = css.split(".pill {", 1)[1].split("}", 1)[0]
    assert "background: transparent" in pill, "the badge must be quiet"


def test_the_drawer_looks_openable_and_animates_the_connection():
    """Opening a card should visibly connect claim to the messages it stands on. That is the
    only motion on the page that carries meaning."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert ".drawer[open] > summary::before" in css and "rotate(90deg)" in css
    assert ".drawer[open] .evidence li" in css and "animation-delay" in css


def test_cards_go_two_up_on_wide_screens():
    """A full-width card holding one line of text is what made the page feel thin."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    block = css.split("@media (min-width: 1100px)", 1)[1].split("}", 1)[0]

    assert "repeat(2, minmax(0, 1fr))" in block


def test_the_hero_puts_claim_and_proof_side_by_side():
    """At 1440px the page was a narrow column with a dead right half."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    html = (METHOD_HTML).read_text(encoding="utf-8")

    assert "hero-claim" in html and "hero-proof" in html
    assert "grid-column: 1 / span 7" in css and "grid-column: 8 / span 5" in css


def test_monospace_is_only_used_for_data():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "--mono:" in css
    assert "Monospace only where the text IS data" in css


# --------------------------------------------------------------- information architecture
def test_one_section_three_states_not_three_sections():
    """"Grounded", "abstained" and "rejected" are one thing — every card the run produced — in
    three outcomes. Stacking them as full-length sections is what made the page endless."""
    html = (METHOD_HTML).read_text(encoding="utf-8")

    assert html.count('class="seg') >= 3
    assert 'role="tablist"' in html
    for count in ("n-grounded", "n-abstained", "n-rejected"):
        assert count in html, "the counts are the story; they belong in the labels"


def test_an_empty_state_is_one_line_not_reserved_height():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    js = METHOD_JS.read_text(encoding="utf-8")

    block = css.split(".empty {", 1)[1].split("}", 1)[0]
    assert "margin: 0" in block and "min-height" not in block
    assert "An empty state must never reserve section height" in js


def test_the_picker_is_over_recordings_and_says_so():
    """A control that looks live claims a capability the judge cannot check and that costs money
    to exercise. It switches between recorded windows, and the page says so."""
    html = LIVE_HTML.read_text(encoding="utf-8")
    js = LIVE_JS.read_text(encoding="utf-8")

    assert "Recorded windows replayed at their true cadence" in html
    assert "No recording of that channel yet" in js, "unknown channel is never a dead end"
    assert "/api/fixtures" in js and "/api/stream" in js


def test_switching_fixture_does_not_reload_the_page():
    js = LIVE_JS.read_text(encoding="utf-8")

    assert "location.reload" not in js and "location.href" not in js
    assert "new EventSource(`/api/stream${query}`)" in js


def test_the_fixture_parameter_cannot_become_a_path():
    """A filename off a query string is untrusted. `Path(...).name` strips any traversal, and the
    target must sit beside the served fixture."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")

    assert 'Path(params.get("fixture", "") or self.fixture.name).name' in serve
    assert "must never become a path" in serve


def test_the_navbar_anchors_every_section_it_lists():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    targets = re.findall(r'class="bar-nav"(.*?)</nav>', html, re.S)
    assert targets, "no nav"
    for href in re.findall(r'href="#([a-z-]+)"', targets[0]):
        assert f'id="{href}"' in html, f"nav points at #{href} which does not exist"


def test_headings_do_not_hide_behind_the_sticky_bar():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "scroll-margin-top" in css


# --------------------------------------------------------------- time-accurate playback
def test_the_stream_is_a_replay_and_says_so():
    """The badge is load-bearing: it is how a viewer knows the source. It is written from the
    server's own `mode`, never from a page-side assumption, and this build only ever replays."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")
    js = LIVE_JS.read_text(encoding="utf-8")

    assert '"mode": "replay"' in serve
    assert "String(open.mode).toUpperCase()" in js, "the badge must echo the server"
    assert "open.speed" in js, "a replay at 8x may not display 1x"


def test_the_playback_cadence_comes_from_the_fixture():
    """"Looks live" is only honest if the timing is the timing the messages actually had."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")

    assert "e.ts_ms - origin" in serve
    assert "bounds[1] - origin" in serve, "a card lands when its window closed, not when it opened"
    assert "No model call, no key, no cost" in serve


def test_the_stream_endpoint_makes_no_model_call():
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")
    body = serve.split("def stream_events")[1].split("\ndef ")[0]

    for forbidden in ("ResponseCache", "provider", "complete(", "httpx"):
        assert forbidden not in body, f"the stream reached for {forbidden}"


def test_the_server_threads_so_a_stream_cannot_block_the_page():
    """An SSE connection is held open for the whole playback. On a single-threaded server the
    page itself would never load while one was running."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")

    assert "ThreadingHTTPServer((host, port), handler)" in serve
    assert "would block every other request" in serve


def test_the_meta_event_is_not_named_open():
    """EventSource reserves `open` for its own connection event, so a custom listener for it
    never fires — and the badge would silently keep its default text."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")
    js = LIVE_JS.read_text(encoding="utf-8")

    assert 'emit("meta"' in serve
    assert 'addEventListener("meta"' in js
    assert 'emit("open"' not in serve


def test_only_the_offered_speeds_are_accepted():
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")

    assert "SPEEDS = (1, 4, 8)" in serve
    assert "if speed not in SPEEDS" in serve


def test_the_chat_column_is_capped_but_the_counter_is_not():
    js = LIVE_JS.read_text(encoding="utf-8")

    assert "MAX_ROWS = 200" in js
    assert "the DOM is capped; the counter is not" in js


def test_a_landing_card_highlights_the_messages_it_cites():
    """The single gesture that is the argument: this cluster, that cause."""
    js = LIVE_JS.read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "highlightCited" in js and "card.evidence" in js
    assert ".msg.cited" in css


def test_the_live_page_never_fabricates():
    """Checked against executable code: the comments name these deliberately, and a guard that
    trips on its own documentation gets deleted rather than fixed."""
    raw = LIVE_JS.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", " ", raw, flags=re.S)
    code = re.sub(r"//.*$", " ", code, flags=re.M)

    assert "Math.random" not in code
    assert "innerHTML" not in code
    assert "textContent, never innerHTML" in raw


def test_the_method_page_is_reachable_and_routed():
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")
    html = LIVE_HTML.read_text(encoding="utf-8")

    assert '"/method"' in serve and "method.html" in serve
    assert 'href="/method"' in html


def test_the_product_page_is_bounded_to_the_viewport():
    """The chat is an unbounded stream. Left to grow it pushed the counter row off the bottom of
    the screen, so the reader lost the one line saying what the flood turned into. The shell is
    fixed at viewport height and only the two columns scroll."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    shell = css.split("\n.live-page {", 1)[1].split("}", 1)[0]   # not `body.live-page`

    assert "height: 100vh" in shell
    assert "overflow: hidden" in shell, "the page itself must never scroll"

    # anchored to the rule itself, not the shared scrollbar rule that also names both
    for selector in ("\n.feed {", "\n.signals {"):
        block = css.split(selector, 1)[1].split("}", 1)[0]
        assert "overflow-y: auto" in block and "min-height: 0" in block, selector

    # min-height:0 on the grid is what lets children scroll instead of the page
    assert "min-height: 0" in css.split("main.two-col {", 1)[1].split("}", 1)[0]
    assert "min-height: 0" in css.split("\n.panel {", 1)[1].split("}", 1)[0]


def test_the_ticker_cannot_be_scrolled_away():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    block = css.split(".ticker {", 1)[1].split("}", 1)[0]

    assert "flex: none" in block, "the counters are the payoff; they stay on screen"


def test_an_empty_signals_column_says_when_to_expect_something():
    """A blank panel for the first minute reads as broken. Analysis windows are 60 seconds, so
    the first card cannot exist before one closes — say that, and show progress toward it."""
    serve = (REPO_ROOT / "src" / "ts" / "report" / "serve.py").read_text(encoding="utf-8")
    js = LIVE_JS.read_text(encoding="utf-8")

    assert '"first_card_ms"' in serve
    assert "The first closes at" in js
    assert "waiting-bar" in js
    assert "This run produced no cards" in js, "a run with nothing must say so, not wait forever"


def test_the_waiting_state_sits_inside_the_signals_column():
    """As a sibling of a flex:1 container it was pushed to the bottom of the panel, far from
    where the reader is looking while waiting for the first card."""
    html = LIVE_HTML.read_text(encoding="utf-8")
    js = LIVE_JS.read_text(encoding="utf-8")

    inner = html.split('<div class="signals" id="signals">', 1)[1].split("</div>", 1)[0]
    assert 'id="signals-empty"' in inner, "the empty state must be a child, not a sibling"
    assert 'document.getElementById("signals").appendChild(empty)' in js


def test_each_pane_is_a_bounded_panel_with_its_own_header():
    """Reversed deliberately. This used to assert the opposite — a field with one hairline and no
    container — on the reading that a box re-introduces a widget. Shown the result, the author
    called it unparseable: an operator scanning signals at a glance needs edges to tell one
    component from another, and the airy treatment read as a single flat wash. Panels it is."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    html = LIVE_HTML.read_text(encoding="utf-8")

    panel = css.split("\n.panel {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid var(--hairline-strong)" in panel
    assert "background: var(--surface-card)" in panel
    assert "border-radius" in panel

    header = css.split(".panel-h {", 1)[1].split("}", 1)[0]
    assert "border-bottom: 1px solid var(--hairline-strong)" in header
    assert "background: var(--canvas-soft)" in header

    assert html.count('class="panel-h"') == 2, "both panes carry a header strip"


def test_structural_lines_are_stronger_than_lines_inside_a_panel():
    """"The lines should be more clear." Structure uses `hairline-strong`; only rules inside a
    panel use the lighter tiers, so the hierarchy is legible rather than uniform."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    for selector in ("\n.panel {", ".panel-h {"):
        block = css.split(selector, 1)[1].split("}", 1)[0]
        assert "hairline-strong" in block, selector
    row = css.split("\n.msg {", 1)[1].split("}", 1)[0]
    assert "border-bottom: 1px solid var(--hairline-soft)" in row, "in-panel rules stay light"


def test_the_counters_are_tiles_not_floating_numbers():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    block = css.split("\n.stat {", 1)[1].split("}", 1)[0]

    assert "border: 1px solid var(--hairline-strong)" in block
    assert "background: var(--surface-card)" in block


def test_the_scrollbars_are_quiet():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "scrollbar-width: thin" in css
    assert "::-webkit-scrollbar" in css
    assert "background: transparent" in css.split("::-webkit-scrollbar-track", 1)[1][:120]


def test_the_signals_header_counts_what_it_shows():
    """It read "Grounded signals · 0" above five visible abstained cards. Same failure as the
    heading that claimed verification over abstentions: a header may not deny its contents."""
    raw = LIVE_HTML.read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)   # comments may name what they fixed
    js = LIVE_JS.read_text(encoding="utf-8")

    assert ">Signals<" in html and "Grounded signals" not in html
    assert 'id="sig-split"' in html
    assert "(state.counts.grounded || 0) + (state.counts.abstained || 0)" in js
    assert "grounded · ${state.counts.abstained" in js


def test_a_run_that_grounds_nothing_says_so_in_place():
    """The agent grounds nothing on any recorded fixture. An empty-looking panel would read as
    loading; the measured result is printed instead, with one click to a system that does."""
    js = LIVE_JS.read_text(encoding="utf-8")

    assert "That is the measured result for" in js
    assert "see the baseline on this window" in js
    assert "notedUngrounded" in js, "it must say this once, not once per card"


def test_card_states_are_distinguished_without_colour():
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    grounded = css.split(".signals .card.is-grounded {", 1)[1].split("}", 1)[0]
    abstained = css.split(".signals .card.is-abstained {", 1)[1].split("}", 1)[0]
    assert "var(--ink)" in grounded and "var(--hairline-strong)" in abstained
    for block in (grounded, abstained):
        for hue in ("--success", "--error", "--orb-"):
            assert hue not in block


# --------------------------------------------------------------- re-render hygiene
def test_every_render_target_is_cleared_before_it_is_filled():
    """Three render functions appended into containers they never emptied, so each fixture or
    system switch stacked another copy of the stat row and another set of table rows under the
    previous ones. The page grew a new block per click."""
    js = METHOD_JS.read_text(encoding="utf-8")

    assert "function clear(node)" in js
    for target in ('getElementById("hero-stats")', 'getElementById("scores-body")',
                   'getElementById("debug-body")'):
        assert f"clear(document.{target})" in js, f"{target} is filled without clearing"


def test_the_badge_says_how_the_page_is_served_not_how_the_run_was_recorded():
    """`result.mode` is the mode the run was captured in — the baseline document literally says
    "record" — so the badge read RECORD forever on a page that only ever serves committed files.
    That reads as a live capture."""
    js = METHOD_JS.read_text(encoding="utf-8")

    assert 'getElementById("mode-badge").textContent = "REPLAY"' in js
    assert 'getElementById("mode-badge").textContent = result.mode' not in js
    # the real value is provenance and still visible, in the debug panel
    assert '["recorded in mode", result.mode]' in js
