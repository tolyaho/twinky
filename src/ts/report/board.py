"""The board and the right rail: one window of chat turned into a few rows and real statistics.

Everything here is deterministic and free. No model, no key, no network — it reads the fixture
that is already on disk, so it works identically in replay and in a live Tier 0 session where no
paid provider is reachable at all.

**What a row is, and what it is not.** A row is *the last thing said or shown before a wave
started* → *what the room said back, grouped, with counts and verbatim messages*. That link is
**temporal**, not causal: it is the nearest preceding speech segment or frame caption, chosen by
timestamp and nothing else. It is not the provenance gate's verdict, it does not mean the trigger
caused the wave, and it is labelled as a time link wherever it is drawn.

The distinction is load-bearing. The agent's grounded cards are a *claim about causation* and
they go through the gate; this attribution is arithmetic on timestamps and goes through nothing,
because it asserts nothing. Blurring the two would be exactly the failure this project keeps
refusing to commit — a card that looks proven because it is next to proven things. So the gate
ledger sits in the same rail, separately, counting what the agent actually verified.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..events import Event
from ..workflow.reduce import STOPWORDS, canonical, group_chat, grouped_summary

RATE_BUCKET_MS = 10_000        # the sparkline's resolution, and the unit "peak burst" is in
MAX_ROWS = 6                   # a board nobody scrolls is a board somebody reads
TOP_SHARE = 0.10               # "concentration" is the share of messages from the top 10%

# A question needs a content word. The bare "ends with ?" rule returns 54 hits on one marlon
# window and they are almost all literally `???` — punctuation is volume, not a question.
#
# A wh-word may be either of the first two tokens, and may carry the contracted `s`. Anchoring
# hard at position zero lost "whats the game" and "yo what game", which are questions anyone
# would recognise; allowing it anywhere picks up "i know what you mean", which is not one.
#
# An auxiliary only counts in first position. Measured on marlon w6, allowing it second turned
# "Capri is 19" and "There is a whole P star right there" into questions — a panel headed
# QUESTIONS TO YOU cannot afford statements in it.
WH_WORDS = frozenset("who whos what whats when whens where wheres why whys how hows which".split())
AUX_WORDS = frozenset("is are do does did can could would should will has have was were "
                      "any anyone".split())


def _content_tokens(text: str) -> List[str]:
    return [t for t in canonical(text).split() if len(t) >= 3 and t not in STOPWORDS]


def is_question(text: str) -> bool:
    """Ends with a question mark, or opens with a question word — and says something either way."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    opening = canonical(stripped).split()[:2]
    asks = (stripped.endswith("?")
            or any(w in WH_WORDS for w in opening)
            or (bool(opening) and opening[0] in AUX_WORDS))
    return asks and bool(_content_tokens(stripped))


def questions(events: Iterable[Event]) -> List[Dict[str, Any]]:
    """The window's questions, grouped so twenty phrasings count once, ranked by how many asked.

    Grouped by shared content tokens rather than by exact text: "what game is this" and "whats
    the game" are one question being asked twice, and a streamer reading a list of forty
    near-identical rows reads none of them.
    """
    asked = [e for e in events if e.type == "chat_message" and is_question(e.text)]
    if not asked:
        return []
    groups = {g.key: g for g in group_chat(asked)}
    placed = {eid for g in groups.values() for eid in g.event_ids}

    out: List[Dict[str, Any]] = []
    for g in groups.values():
        out.append({"text": g.samples[0], "count": g.count, "event_ids": g.event_ids,
                    "variants": g.samples, "ts_ms": g.first_ts_ms})
    for e in asked:                                    # an unmatched question still got asked
        if e.event_id not in placed:
            out.append({"text": e.text, "count": 1, "event_ids": [e.event_id],
                        "variants": [e.text], "ts_ms": e.ts_ms})
    out.sort(key=lambda q: (-q["count"], q["ts_ms"], q["text"]))
    return out


def _overlaps(trigger_text: str, group: Dict[str, Any]) -> bool:
    """Does the trigger literally contain what chat is typing?

    Word-level for token groups, prefix-level for prefix groups, because a screen caption reading
    *the partial word `para_`* and forty messages beginning `para` are the same four characters
    and pretending otherwise loses the one row that carries the whole thesis.
    """
    words = set(_content_tokens(trigger_text or ""))
    if group["rule"] == "prefix":
        body = group["key"][2:]
        return any(w.startswith(body) for w in words)
    return group["key"][2:] in words


def _trigger_for(index, group: Dict[str, Any], start: int) -> Optional[Dict[str, Any]]:
    """The moment a wave is attached to, and how strong that attachment is.

    Two tiers, and the difference is drawn on screen rather than smoothed over:

      `matched`    the trigger text contains the word chat is typing. That is a real link.
      `preceding`  merely the last thing said or shown before the wave started. That is
                   adjacency, and adjacency is not cause.

    Nearest-preceding alone is not good enough, and the failure is not hypothetical: on
    `stableronaldo` w9 it attached forty-one people brute-forcing an on-screen word puzzle to a
    caption about *"three people sleeping in a dimly lit room"*. A row header reads as causal
    however it is captioned, so a board that cannot tell the two apart asserts something false.
    Neither tier goes through the provenance gate, because neither claims causation — the gate
    judges the agent's cards, and its ledger is in the rail beside this.
    """
    prior = list(index.window(start, group["first_ts_ms"] + 1,
                              types=["transcript_segment", "frame_caption"]))
    if not prior:
        return None

    matched = [e for e in prior if _overlaps(e.text, group)]
    e, link = (matched[-1], "matched") if matched else (prior[-1], "preceding")
    return {"kind": "speech" if e.type == "transcript_segment" else "screen", "link": link,
            "event_id": e.event_id, "ts_ms": e.ts_ms, "text": e.text}


def board(index, start: int, end: int, *, max_rows: int = MAX_ROWS) -> Dict[str, Any]:
    """One window as rows. Groups with a preceding trigger become rows; the rest are unattributed.

    Rows carry the group's own `count`, `event_ids` and verbatim samples untouched — the feed
    highlights those ids, so anything invented here would highlight the wrong messages.
    """
    chat = list(index.window(start, end, types=["chat_message"]))
    groups = group_chat(chat)
    summary = grouped_summary(chat, groups)

    rows: List[Dict[str, Any]] = []
    unattributed: List[Dict[str, Any]] = []
    for g in groups:
        row = g.to_dict()
        trigger = _trigger_for(index, row, start)
        (rows if trigger else unattributed).append({"trigger": trigger, **row})

    # Rows with the same trigger are one moment the room reacted to, not several.
    merged: List[Dict[str, Any]] = []
    for row in rows:
        prior = next((m for m in merged
                      if m["trigger"]["event_id"] == row["trigger"]["event_id"]), None)
        if prior is None:
            merged.append({"trigger": row["trigger"], "groups": [row],
                           "count": row["count"], "first_ts_ms": row["first_ts_ms"]})
        else:
            prior["groups"].append(row)
            prior["count"] += row["count"]
            # One matched group is enough to make the moment a real link; the merged row is
            # only as weak as its strongest member, never as weak as its first.
            if row["trigger"]["link"] == "matched":
                prior["trigger"] = row["trigger"]
    # Matched rows first: a row that names the word chat is typing outranks a bigger row that
    # only happened to be nearby.
    merged.sort(key=lambda m: (m["trigger"]["link"] != "matched", -m["count"], m["first_ts_ms"]))
    shown = merged[:max_rows]

    return {
        "window_ms": [start, end],
        "rows": shown,
        "unattributed": sorted(unattributed, key=lambda g: (-g["count"], g["first_ts_ms"])),
        "footer": {
            "messages": summary["messages"],
            "rows": len(shown),
            "singletons": summary["ungrouped"],
            # A board that shows six of nine rows has to say so, or six reads as all of them.
            "rows_hidden": max(0, len(merged) - len(shown)),
        },
    }


def _buckets(chat: Sequence[Event], start: int, end: int) -> List[int]:
    n = max(1, -(-(end - start) // RATE_BUCKET_MS))
    out = [0] * n
    for e in chat:
        i = min(n - 1, max(0, (e.ts_ms - start) // RATE_BUCKET_MS))
        out[i] += 1
    return out


def rail(index, start: int, end: int, *, cards: Optional[Sequence[Dict[str, Any]]] = None,
         seen_authors: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Everything on the right-hand side, all of it measured from the window.

    `seen_authors` is who had already spoken before this window, so "new chatters" means new.
    A spike in new names is a raid or a clip landing, and the raw message count hides it
    completely — five hundred messages from five people is a different stream from five hundred
    from five hundred.
    """
    chat = list(index.window(start, end, types=["chat_message"]))
    groups = group_chat(chat)
    summary = grouped_summary(chat, groups)

    authors: Dict[str, int] = {}
    for e in chat:
        authors[e.author] = authors.get(e.author, 0) + 1
    before = set(seen_authors or ())
    counts = sorted(authors.values(), reverse=True)
    top_n = max(1, int(len(counts) * TOP_SHARE)) if counts else 0
    concentration = (sum(counts[:top_n]) / len(chat)) if chat else 0.0

    buckets = _buckets(chat, start, end)
    peak = max(buckets) if buckets else 0

    speech = list(index.window(start, end, types=["transcript_segment"]))
    frames = list(index.window(start, end, types=["frame_caption"]))

    # The gate ledger. Rejections by code, from the recorded run — the strongest agent-engineering
    # artifact on the page, and the only part of the rail that is about the agent rather than the
    # audience. Counted, never editorialised.
    ledger: Dict[str, int] = {}
    verified = abstained = rejected = 0
    for card in cards or []:
        gate = card.get("gate") or {}
        if not gate.get("ok"):
            rejected += 1
            for violation in gate.get("violations") or []:
                key = violation.get("code") if isinstance(violation, dict) else str(violation)
                ledger[key] = ledger.get(key, 0) + 1
        elif card.get("type") in (None, "none"):
            abstained += 1
        else:
            verified += 1

    reaction = next((g.count for g in groups if g.rule == "reaction"), 0)
    return {
        "messages": len(chat),
        "rate": buckets,
        "peak_burst": peak,
        "peak_per_second": round(peak / (RATE_BUCKET_MS / 1000), 2),
        "unique_chatters": len(authors),
        "new_chatters": len([a for a in authors if a not in before]),
        "messages_per_chatter": round(len(chat) / len(authors), 2) if authors else 0.0,
        "concentration": round(concentration, 3),
        "composition": {"messages": summary["messages"], "groups": summary["groups"],
                        "singletons": summary["ungrouped"]},
        "reaction_wave": reaction,
        "questions": questions(chat),
        # Zero speech segments is the truth on stableronaldo, and "silent window" is a finding
        # about the stream, not a gap in the data. It is stated rather than left blank.
        "speech_segments": len(speech),
        "silent": not speech,
        "frame_captions": [{"id": e.event_id, "ts_ms": e.ts_ms, "text": e.text} for e in frames],
        "gate": {"verified": verified, "abstained": abstained, "rejected": rejected,
                 "codes": dict(sorted(ledger.items()))},
    }


def windows(index, *, window_ms: int = 60_000) -> List[List[int]]:
    """The window tiles a fixture is cut into: half-open `[start, end)`, aligned to the first
    event so replay and the board agree on where a window begins."""
    out: List[List[int]] = []
    start = index.start_ms
    while start <= index.end_ms:
        out.append([start, start + window_ms])
        start += window_ms
    return out
