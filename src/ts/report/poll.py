"""The one outward action: approve → draft poll.

This closes the last link of the product invariant — multimodal stream context, grounded
audience signal, evidence, *streamer action*. Without it the chain ends at a label reading
"pending_approval" that nothing can act on.

Nothing here posts. There is no client, no token and no network call in this module by design:
a draft is produced, a human reads it, and copying it into Twitch is their deliberate act.
Ground rule 06 — polls, highlights and replies stay drafts.

The draft is built server-side and shipped with the payload rather than assembled in the
browser, so the thing a streamer approves is derived deterministically from verified evidence
and can be tested.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..provenance import UNKNOWN

# Twitch's own limits on a poll, as recalled rather than sourced — see RISKS #25. Nothing posts,
# so a wrong cap costs nothing today; it must be checked against the API docs before any real
# integration. The caps are applied visibly: anything trimmed is reported in `warnings`.
MAX_OPTIONS = 5
MIN_OPTIONS = 2
MAX_QUESTION_CHARS = 60
MAX_OPTION_CHARS = 25


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_draft(card: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A verified audience-answer card becomes a poll a streamer can approve.

    Returns None when the card cannot honestly become a poll — fewer than two options, or a
    distribution that carries no counts. A poll with one choice is not a poll.
    """
    if card.get("type") != "audience_answer":
        return None

    distribution = card.get("distribution") or {}
    counted = {str(k): v for k, v in distribution.items() if isinstance(v, (int, float)) and v > 0}
    if len(counted) < MIN_OPTIONS:
        return None

    # Deterministic: by votes descending, then by label, so the same card always yields the
    # same draft and two machines agree on what was trimmed.
    ranked = sorted(counted.items(), key=lambda kv: (-kv[1], kv[0]))
    warnings: List[str] = []

    # Shares are over everything chat said, not over what survived the cap. Renormalising would
    # print a percentage that disagrees with the card sitting directly above it on the page.
    total = sum(counted.values())

    if len(ranked) > MAX_OPTIONS:
        dropped = [label for label, _ in ranked[MAX_OPTIONS:]]
        warnings.append(
            f"{len(ranked)} options; a poll takes {MAX_OPTIONS}. "
            f"Dropped the lowest: {', '.join(dropped)}. Shares below still count every vote, so "
            "they do not add to 100%.")
        ranked = ranked[:MAX_OPTIONS]
    options = []
    for label, votes in ranked:
        short = _truncate(label, MAX_OPTION_CHARS)
        if short != label:
            warnings.append(f"Option shortened to fit: {label!r} → {short!r}.")
        options.append({"label": short, "votes": votes,
                        "share": round(votes / total, 3) if total else 0.0})

    trigger = card.get("trigger") or {}
    source = trigger.get("quote") if (trigger.get("event_id") or UNKNOWN) != UNKNOWN else None
    question = _truncate(source or card.get("title") or "Chat, which one?", MAX_QUESTION_CHARS)
    if source is None:
        warnings.append(
            "No established cause, so the question is the card title rather than what the "
            "streamer actually said. Read it before approving.")

    return {
        "signal_id": card.get("signal_id"),
        "question": question,
        "options": options,
        "total_votes": total,
        "evidence": list(card.get("evidence") or []),
        "trace_id": card.get("trace_id"),
        "state": "pending_approval",
        "posts_anything": False,
        "warnings": warnings,
    }


def attach_drafts(cards: List[Dict[str, Any]]) -> int:
    """Attach a draft to every card that already carries a `draft_poll` action.

    The agent decides a card warrants an action; this only prepares what the human will read.
    """
    attached = 0
    for card in cards:
        if (card.get("action") or {}).get("kind") != "draft_poll":
            continue
        draft = build_draft(card)
        if draft is not None:
            card["poll_draft"] = draft
            attached += 1
    return attached
