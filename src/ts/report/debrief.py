"""Post-stream debrief.

The self-contained artifact. A live dashboard never *finishes*, and End-to-End Quality asks for
a realistic execution ending in a result the user can actually use. This is also the product's
second thesis made concrete: Twitch deletes past broadcasts in 7 days (regular, and off by
default), 14 days (Affiliate) or 60 days (Partner), and the chat replay dies with the VOD.

Everything here is derived from cards that already passed the provenance gate. No model call, no
new claim: the debrief reorganises verified output, it does not produce any. That is what makes
it cheap, deterministic, and impossible to hallucinate into.

Sections:
  - audience answers, with the distribution and the question that caused them
  - questions chat asked that were never answered  (needs the transcript: a chat-only system
    structurally cannot produce this section)
  - reaction waves, each with its timestamp and triggering quote
  - warnings, including the ones with no provable cause - abstention made visible
  - clip candidates: the densest audience responses that are tied to a stream moment
  - recurring themes across the session
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..events import EventIndex
from ..provenance import UNKNOWN, normalize

CLIP_LIMIT = 5
THEME_MIN_CARDS = 2
THEME_MIN_TOKEN_LEN = 3

# Deliberately tiny and visible rather than a package dependency or a model call: only the
# function words long enough to survive THEME_MIN_TOKEN_LEN, in the two languages the fixtures
# actually contain. Extend it from observed noise, never pre-emptively.
STOPWORDS = frozenset({
    "the", "and", "for", "you", "this", "that", "with", "but", "not", "are", "was",
    "или", "что", "как", "это", "там", "тут", "все", "они", "она", "его", "ещё", "еще",
})

SECTION_TITLES = [
    ("audience_answers", "Audience answers"),
    ("unanswered_questions", "Questions chat asked that were never answered"),
    ("reaction_waves", "Reaction waves"),
    ("warnings", "Warnings"),
    ("clip_candidates", "Clip candidates"),
    ("recurring_themes", "Recurring themes"),
]

_TYPE_SECTIONS = [
    ("audience_answer", "audience_answers"),
    ("unanswered_question", "unanswered_questions"),
    ("reaction", "reaction_waves"),
    ("warning", "warnings"),
]


def timecode(ts_ms: int, start_ms: int) -> str:
    """Offset from the start of the stream. A clip candidate is useless without one."""
    seconds = max(0, (int(ts_ms) - int(start_ms)) // 1000)
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def _entry(card: Dict[str, Any], start_ms: int, index: Optional[EventIndex]) -> Dict[str, Any]:
    trigger = dict(card.get("trigger") or {})
    event_id = trigger.get("event_id")

    ts_ms, ts_source = None, "none"
    event = index.get(event_id) if (index is not None and event_id and event_id != UNKNOWN) else None
    if event is not None:
        ts_ms, ts_source = event.ts_ms, "trigger"
    elif card.get("window_ms"):
        # Coarser, and labelled as such: the window start is where to begin looking, not the
        # moment the signal happened.
        ts_ms, ts_source = int(card["window_ms"][0]), "window"

    return {
        "signal_id": card.get("signal_id"),
        "type": card.get("type"),
        "title": card.get("title"),
        "distribution": card.get("distribution"),
        "trigger": trigger,
        "evidence": list(card.get("evidence") or []),
        "confidence": card.get("confidence"),
        "trace_id": card.get("trace_id"),
        "ts_ms": ts_ms,
        "ts_source": ts_source,
        "at": timecode(ts_ms, start_ms) if ts_ms is not None else None,
    }


def _sort_key(entry: Dict[str, Any]) -> tuple:
    return (entry["ts_ms"] if entry["ts_ms"] is not None else 0, str(entry["signal_id"]))


def _clip_candidates(entries: Sequence[Dict[str, Any]], limit: int = CLIP_LIMIT
                     ) -> List[Dict[str, Any]]:
    """A dense audience response tied to a stream moment.

    Density comes from the number of distinct messages the card cites, which is chat velocity
    already measured and already verified. A card whose trigger is `unknown` is deliberately
    excluded: there is no moment to clip.
    """
    tied = [e for e in entries if (e["trigger"].get("event_id") or UNKNOWN) != UNKNOWN]
    return sorted(tied, key=lambda e: (-len(e["evidence"]), _sort_key(e)))[:limit]


def _tokens(entry: Dict[str, Any]) -> set:
    """Words the audience or the streamer actually used.

    Card titles are excluded on purpose. A title is prose the model wrote, so counting its words
    measures the model's phrasing habits, not the session - the first run of this section
    returned "chat", "says" and "the". Distribution keys are the audience's own vocabulary and
    the trigger quote is verbatim transcript, and neither was authored by the summariser.
    """
    words = normalize(str((entry.get("trigger") or {}).get("quote") or "")).split()
    for key in (entry.get("distribution") or {}):
        words += normalize(str(key)).split()
    return {w for w in words
            if len(w) >= THEME_MIN_TOKEN_LEN and not w.isdigit() and w not in STOPWORDS}


def _recurring_themes(entries: Sequence[Dict[str, Any]],
                      min_cards: int = THEME_MIN_CARDS) -> List[Dict[str, Any]]:
    """A term carried by two or more separate verified signals.

    Deliberately a word count, not a clustering pass. Embedding clustering was tried on this
    data in Oct 2025 and again in Mar 2026 and gave unstable clusters; a rule a streamer can
    check by eye is worth more here than a similarity score they cannot.

    An empty section is the common and correct outcome on a short session: three unrelated
    signals in half a minute have no recurring theme, and saying so beats padding the document.
    """
    by_term: Dict[str, List[str]] = {}
    for entry in entries:
        for term in _tokens(entry):
            by_term.setdefault(term, []).append(str(entry["signal_id"]))
    return sorted(
        ({"term": term, "signal_ids": sorted(ids), "cards": len(ids)}
         for term, ids in by_term.items() if len(ids) >= min_cards),
        key=lambda t: (-t["cards"], t["term"]),
    )


def build(cards: List[Dict[str, Any]], meta: Dict[str, Any],
          index: Optional[EventIndex] = None) -> Dict[str, Any]:
    """Roll VERIFIED cards up into the post-stream document.

    Pass only cards that cleared the gate. The debrief is what a streamer reads after the
    broadcast; a card whose evidence did not check out has no business in it. The eval scores
    rejected cards too, but that is measurement, not the product.
    """
    start_ms = int(meta.get("start_ms") or 0)
    entries = sorted((_entry(c, start_ms, index) for c in cards), key=_sort_key)

    sections: Dict[str, List[Dict[str, Any]]] = {key: [] for key, _ in SECTION_TITLES}
    for card_type, section in _TYPE_SECTIONS:
        sections[section] = [e for e in entries if e["type"] == card_type]
    sections["clip_candidates"] = _clip_candidates(entries)
    sections["recurring_themes"] = _recurring_themes(entries)

    return {
        "fixture_id": meta.get("fixture_id"),
        "channel": meta.get("channel"),
        "start_ms": start_ms,
        "duration_ms": meta.get("duration_ms"),
        "verified_cards": len(entries),
        "sections": sections,
    }


# --------------------------------------------------------------------------- rendering
def _distribution_line(distribution: Dict[str, Any]) -> str:
    total = sum(v for v in distribution.values() if isinstance(v, (int, float)))
    parts = []
    for key, value in distribution.items():
        share = f" ({value / total:.0%})" if total else ""
        parts.append(f"**{key}** {value}{share}")
    return " · ".join(parts)


def _render_entry(entry: Dict[str, Any]) -> List[str]:
    at = entry["at"] or "--:--:--"
    approx = " *(window start, not the exact moment)*" if entry["ts_source"] == "window" else ""
    lines = [f"### `{at}` {entry['title'] or entry['type']}{approx}"]

    if entry.get("distribution"):
        lines.append(f"- {_distribution_line(entry['distribution'])}")

    trigger = entry["trigger"]
    event_id = trigger.get("event_id") or UNKNOWN
    if event_id == UNKNOWN:
        lines.append("- Cause: **not established.** Chat reacted to something the system could "
                     "not tie to a stream moment.")
    else:
        quote = trigger.get("quote")
        kind = trigger.get("kind") or "event"
        lines.append(f"- Cause ({kind} `{event_id}`): " + (f"“{quote}”" if quote else "—"))

    lines.append(f"- Evidence: {len(entry['evidence'])} messages "
                 f"({', '.join(f'`{m}`' for m in entry['evidence'][:6])}"
                 f"{', …' if len(entry['evidence']) > 6 else ''})")
    if entry.get("confidence") is not None:
        lines.append(f"- Confidence: {entry['confidence']} · trace `{entry.get('trace_id')}`")
    return lines + [""]


def render_markdown(document: Dict[str, Any]) -> str:
    head = document.get("fixture_id") or "stream"
    lines = [f"# Post-stream debrief — {head}", ""]
    if document.get("channel"):
        lines.append(f"Channel `{document['channel']}` · "
                     f"{document['verified_cards']} verified signals")
        lines.append("")
    lines += ["Every line below is derived from a card that passed the provenance gate. Nothing "
              "here is generated: timecodes come from the triggering event, and every claim "
              "lists the message ids behind it.", ""]

    if not document["verified_cards"]:
        lines += ["## No verified signals", "",
                  "The run produced no card whose evidence checked out. That is a result, not an "
                  "error — it is what the system is supposed to say when it cannot prove "
                  "anything.", ""]
        return "\n".join(lines)

    for key, title in SECTION_TITLES:
        section = document["sections"][key]
        lines += [f"## {title}", ""]
        if not section:
            lines += ["_Nothing in this run._", ""]
            continue
        if key == "recurring_themes":
            lines += ["| term | signals |", "|---|---:|"]
            lines += [f"| {t['term']} | {t['cards']} |" for t in section] + [""]
            continue
        for entry in section:
            lines += _render_entry(entry)

    return "\n".join(lines)
