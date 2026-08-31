"""Does the page actually work, after twenty iterations of editing it?

A single `document.getElementById("...")` that returns `null` throws on the next property access
and kills the script — mid-stream, in front of whoever is watching. Nothing else in this suite
catches that: the server tests assert payloads, and the CSS tests assert tokens. This asserts the
wiring between the markup and the code that drives it.

Written the iteration before the demo is filmed, for exactly that reason.
"""
import html.parser
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src/ts/report/static"
PAGES = {"live.js": "index.html", "method.js": "method.html"}

# Created by the code itself and read behind a null check, so it is correctly absent from markup.
RUNTIME_CREATED = {"signals-finding"}


def _ids(page):
    return set(re.findall(r'id="([^"]+)"', (STATIC / page).read_text(encoding="utf-8")))


@pytest.mark.parametrize("script,page", sorted(PAGES.items()))
def test_every_element_the_script_reaches_for_exists(script, page):
    source = (STATIC / script).read_text(encoding="utf-8")
    referenced = set(re.findall(r'getElementById\(\s*["\']([^"\']+)["\']', source))

    missing = sorted(referenced - _ids(page) - RUNTIME_CREATED)

    assert not missing, f"{script} reads ids that {page} does not define: {missing}"


def test_the_runtime_created_id_is_guarded():
    """It is legitimate for the code to create its own node — as long as the read that precedes
    it cannot explode."""
    live = (STATIC / "live.js").read_text(encoding="utf-8")

    assert 'note.id = "signals-finding"' in live
    assert "if (!note) {" in live


def test_the_counter_ids_built_at_runtime_all_resolve():
    """`c-${name}` and `n-${name}` are assembled from literal lists. A name added to one of those
    lists without a matching element is the same null crash, one level less visible."""
    live = (STATIC / "live.js").read_text(encoding="utf-8")
    method = (STATIC / "method.js").read_text(encoding="utf-8")

    counters = re.search(r'for \(const name of \[([^\]]+)\]\)', live)
    names = re.findall(r'"([^"]+)"', counters.group(1))
    assert names, "the counter loop changed shape; this guard needs updating with it"
    assert not [n for n in names if f"c-{n}" not in _ids("index.html")]

    buckets = re.search(r"buckets = \{([^}]+)\}", method)
    keys = re.findall(r"(\w+):", buckets.group(1))
    assert keys
    assert not [k for k in keys if f"n-{k}" not in _ids("method.html")]


@pytest.mark.parametrize("page", ["index.html", "method.html", "philosophy.html"])
def test_the_markup_is_balanced(page):
    """A stray unclosed section silently swallows everything after it. One was introduced while
    moving the moderation panel below the results, and only a parser caught it."""
    class Check(html.parser.HTMLParser):
        VOID = {"meta", "link", "br", "img", "input", "hr", "source", "path", "circle", "line",
                "rect", "polyline", "use", "col", "area", "embed", "track", "wbr"}

        def __init__(self):
            super().__init__()
            self.stack, self.bad = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in self.VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            elif tag in self.stack:
                self.bad.append(tag)
                self.stack.remove(tag)

    check = Check()
    check.feed((STATIC / page).read_text(encoding="utf-8"))

    assert not check.stack, f"{page} leaves {check.stack} unclosed"
    assert not check.bad, f"{page} closes {check.bad} out of order"


@pytest.mark.parametrize("script", sorted(PAGES))
def test_no_script_writes_untrusted_text_as_html(script):
    """Chat is hostile input and appears on both pages."""
    from conftest import strip_js_comments

    assert "innerHTML" not in strip_js_comments((STATIC / script).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ keyboard access
# Clicking a row to light up the messages behind it is the product's central gesture. Four of
# those targets were plain <article> and <div> elements with a click handler: reachable with a
# mouse and by nothing else.

def test_every_rich_click_target_goes_through_the_activatable_helper(js_source):
    js = js_source("live.js")

    assert "function activatable(" in js
    # the four rich regions: a board row, the unattributed block, a live group line, a question
    assert js.count("activatable(") == 5, "a rich click target is bypassing the helper"
    for bypass in ('box.addEventListener("click"', 'line.addEventListener("click"',
                   'row.addEventListener("click"'):
        assert bypass not in js, f"{bypass} is a mouse-only target again"


def test_the_helper_makes_a_region_operable_not_merely_clickable(js_source):
    js = js_source("live.js")
    body = js.split("function activatable", 1)[1].split("\nfunction ", 1)[0]

    assert 'setAttribute("role", "button")' in body
    assert 'setAttribute("tabindex", "0")' in body
    assert 'setAttribute("aria-label"' in body, "a focusable region needs to say what it does"
    assert '"Enter"' in body and '" "' in body, "Enter and Space both activate a button"
    assert "preventDefault()" in body, "Space would scroll the page instead"


def test_each_target_says_what_activating_it_will_do():
    """`aria-label="Highlight the 27 messages behind this row"` — not "row"."""
    js = (STATIC / "live.js").read_text(encoding="utf-8")

    for label in ("messages behind this row", "unattributed messages",
                  "messages in ${g.label}", "messages asking"):
        assert label in js, f"a target has no meaningful label: {label}"


def test_focus_is_restyled_and_never_removed():
    # Seventh time: the comment recording that `#rejected-rail` was removed contains the
    # selector it says is gone. Assert against rules, explain in prose.
    css = re.sub(r"/\*.*?\*/", " ", (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)

    assert ":focus-visible" in css
    assert "outline: 2px solid var(--focus-ring)" in css
    assert "outline: none" not in css and "outline: 0" not in css


# ------------------------------------------------------- reduced motion, in JS as well as CSS

def test_the_citation_scroll_respects_reduced_motion(js_source):
    """CSS cannot reach this. `scrollIntoView({behavior: "smooth"})` passes the behaviour
    explicitly and overrides the stylesheet's `scroll-behavior: auto`, so a reader who asked for
    less motion still got a smooth scroll on every citation — the gesture the product rests on."""
    js = js_source("live.js")

    assert "prefers-reduced-motion" in js, "live.js never consulted the preference"
    assert 'stillPreferred() ? "auto" : "smooth"' in js
    assert 'behavior: "smooth" }' not in js, "an unconditional smooth scroll is back"


def test_reduced_motion_still_renders_the_stage(js_source):
    """It means "do not animate", not "do not show me the content". `renderStage` used to skip
    `stagePlay` entirely, so the Method page's only real-data demonstration rendered as an
    unhidden, completely empty box."""
    js = js_source("method.js")

    assert "function stagePlay(hero, still)" in js
    assert "stagePlay(hero, still)" in js
    body = js.split("function stagePlay", 1)[1].split("\nfunction ", 1)[0]
    assert "still ? run() : stageTimers.push" in body, "the still path must render immediately"
    # every beat goes through the helper, or one of them stays animation-only
    assert body.count("after(") == 4, "a stage beat is bypassing the reduced-motion path"


def test_the_preference_is_read_when_used_not_cached_at_load(js_source):
    """It can change while the page is open."""
    js = js_source("live.js")

    assert "const stillPreferred = () =>" in js, "a cached boolean goes stale"


# Shared chrome: the same component, deliberately present on both pages. `#rail` was NOT this —
# it named the Method page's card rail and the product page's statistics rail, two different
# things, and an id beats `.panel-rail .rail` on specificity, so the product rail was silently
# laid out as a two-column grid inside a ~259px column.
SHARED_CHROME = {"debug", "debug-body", "debug-toggle", "mode-badge", "picker", "picker-chips",
                 "picker-input", "picker-list", "picker-note", "signals"}


def test_an_id_shared_between_pages_is_the_same_component():
    """Anything new sharing a name across pages is a `#rail` waiting to happen: one stylesheet,
    two meanings, and the id wins on specificity wherever they disagree."""
    shared = _ids("index.html") & _ids("method.html")

    unexpected = sorted(shared - SHARED_CHROME)
    assert not unexpected, (
        f"{unexpected} now names something on both pages — confirm it is the same component and "
        f"add it to SHARED_CHROME, or rename one of them")


def test_no_stylesheet_rule_targets_an_id_that_exists_nowhere():
    """`#rejected-rail` and `#abstained-rail` were styled and never rendered."""
    import re

    # Seventh time: the comment recording that `#rejected-rail` was removed contains
    # the selector it says is gone. Assert against rules, explain in prose.
    css = re.sub(r"/\*.*?\*/", " ",
                 (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)
    live = _ids("index.html") | _ids("method.html") | _ids("philosophy.html")
    # ids created at runtime by the scripts
    live |= set(re.findall(r'\.id = "([^"]+)"',
                           (STATIC / "live.js").read_text(encoding="utf-8")))

    # `#a7e5d3` is a colour, not a selector. Ids cannot be pure hex of those lengths.
    def is_colour(token):
        return len(token) in (3, 4, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in token)

    styled = {s for s in re.findall(r"#([a-zA-Z][\w-]*)", css) if not is_colour(s)}
    orphans = sorted(styled - live)

    assert not orphans, f"styled but never rendered: {orphans}"


def test_no_class_is_styled_that_no_page_renders():
    """`#rejected-rail` was styled for weeks and rendered nowhere; the same rot happens to
    classes, and dead CSS reads as a feature to whoever edits next.

    Class names are built four ways — a markup attribute, a plain argument to `el()`, a ternary,
    and a template literal like `card is-${state}`. Guessing which is which produced fourteen
    false positives on the first attempt, so every string and template literal in the scripts is
    treated as a possible source, and interpolated prefixes are resolved from the literal itself.
    """
    import re

    css = re.sub(r"/\*.*?\*/", " ", (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)
    styled = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", css))

    rendered, prefixes = set(), set()
    for page in ("index.html", "method.html", "philosophy.html"):
        for attr in re.findall(r'class="([^"]*)"', (STATIC / page).read_text(encoding="utf-8")):
            rendered |= set(attr.split())
    for js in ("live.js", "method.js"):
        src = re.sub(r"/\*.*?\*/", " ", (STATIC / js).read_text(encoding="utf-8"), flags=re.S)
        for lit in re.findall(r'"([^"\n]*)"', src) + re.findall(r"`([^`]*)`", src):
            prefixes |= set(re.findall(r"([a-z][\w-]*-)\$\{", lit))
            for part in re.sub(r"\$\{[^}]*\}", " ", lit).split():
                if re.fullmatch(r"[a-z][\w-]*", part):
                    rendered.add(part)

    dead = sorted(c for c in styled - rendered
                  if not any(c.startswith(p) for p in prefixes))

    assert not dead, f"styled but rendered by nothing: {dead}"
