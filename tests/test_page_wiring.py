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
