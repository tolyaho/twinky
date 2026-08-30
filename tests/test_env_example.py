"""`.env.example` — the file someone copies after rotating credentials.

It set `TS_TEXT_MODEL=deepseek-v4-flash` while every recorded response came from `gpt-4.1-nano`.
Copying it to `.env` was enough to turn every cache entry into a miss and stop `make eval`
reproducing — the one property the submission rests on. Verified 2026-08-30 by doing it.

So the rule this file enforces is: **the example must be safe to copy.**
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / ".env.example"

# Variables whose value is part of a cache key. An uncommented assignment to any of these is the
# trap that was there before.
CACHE_KEY_VARS = {"TS_TEXT_MODEL", "TS_VISION_MODEL"}


def _assignments(text):
    r"""Only live assignments — commented lines are documentation, not configuration.

    `[ \t]*` and not `\s*` after the `=`: `\s` matches newlines, so an empty value silently
    swallowed the next line and every key appeared to hold a comment as its value.
    """
    return dict(re.findall(r"^[ \t]*([A-Z0-9_]+)[ \t]*=[ \t]*(.*)$", text, re.M))


def test_no_model_name_is_set_live():
    """The whole defect. The code defaults to the recorded models when these are unset."""
    live = _assignments(EXAMPLE.read_text(encoding="utf-8"))

    offenders = sorted(CACHE_KEY_VARS & set(live))
    assert not offenders, f"{offenders} would change the cache key for anyone who copies this"


def test_the_recorded_models_are_still_the_code_defaults():
    """The example tells the reader to leave the variables unset *because* the defaults are the
    recorded ones. If a default moves, that advice becomes wrong."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from ts.workflow.agent import DEFAULT_TEXT_MODEL

    assert DEFAULT_TEXT_MODEL == "gpt-4.1-nano"
    assert "gpt-4.1-nano" in EXAMPLE.read_text(encoding="utf-8")


def test_every_variable_the_code_reads_is_documented():
    """Four were missing, including the base URL — without which an OpenAI key is sent to
    DeepSeek and returns 401. That is not a hypothetical; it happened during a record phase."""
    text = EXAMPLE.read_text(encoding="utf-8")
    read = set()
    for path in list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        read |= set(re.findall(r'os\.(?:environ\.get|getenv)\(\s*["\']([A-Z0-9_]+)["\']', source))
        read |= set(re.findall(r'os\.environ\[\s*["\']([A-Z0-9_]+)["\']', source))

    # OPENAI_API_KEY is read only by the embeddings arm's record path, which documents itself.
    missing = sorted(v for v in read - {"OPENAI_API_KEY"} if v not in text)
    assert not missing, f".env.example never mentions {missing}"


def test_the_base_url_points_where_the_recordings_were_made():
    live = _assignments(EXAMPLE.read_text(encoding="utf-8"))

    assert live.get("TS_LLM_BASE_URL", "").startswith("https://api.openai.com"), \
        "the built-in default is DeepSeek's; an OpenAI key sent there returns 401"


def test_no_key_has_a_value():
    live = _assignments(EXAMPLE.read_text(encoding="utf-8"))

    for name, value in live.items():
        if name.endswith("_KEY"):
            assert value.strip() == "", f"{name} has a value in a committed example file"


def test_nothing_documented_here_is_unused():
    """`TS_ESCALATION_MODEL` sat here describing a model nothing reads, which reads as a feature
    that exists."""
    text = EXAMPLE.read_text(encoding="utf-8")

    assert "TS_ESCALATION_MODEL" not in text
