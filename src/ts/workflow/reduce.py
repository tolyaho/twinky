"""Deterministic noise reduction.

Not an LLM job. This is the January 2026 cost finding turned into a component: per-message
inference cost ~$0.05 per 5 minutes on an active chat with a ~30s latency tail under load.
Understand the event once, aggregate the reactions to it.

Counts and source ids are preserved so the provenance gate and the answer distributions still
have real evidence to point at.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ..events import Event

_EMOTE_RUN = re.compile(r"(\b\w+\b)(\s+\1\b)+", flags=re.UNICODE)
_CHAR_RUN = re.compile(r"(.)\1{2,}", flags=re.UNICODE)
# "ахахахаха" and "ахахаха" are the same reaction; the repeating unit is a syllable,
# not a character, so fold any 1-4 char group repeated 3+ times down to two repeats.
_NGRAM_RUN = re.compile(r"(.{1,4}?)\1{2,}", flags=re.UNICODE)


EMPTY_KEY = "∅"          # punctuation-only messages; kept so counts still sum
EMPTY_SAMPLE = "(punctuation only)"


def _strip_punctuation(text: str) -> str:
    """Remove Unicode punctuation, keep symbols.

    The previous rule was `[^\\w\\s]+`, which also deleted every symbol — so an emote-only
    message canonicalised to nothing and was dropped entirely. On Twitch that is the most common
    reaction there is, and this module claims to preserve counts. Emoji are category `S*`, so
    keeping symbols keeps them; `!!!` is category `P*` and still collapses away.
    """
    return "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)


def canonical(text: str) -> str:
    """Collapse a chat message to its semantic skeleton.

    'AHAHAHAHA', 'ahahaha' and 'AHAHA AHAHA' all collapse together; 'left' and 'LEFT!!!' do too.
    An emote run collapses the same way: '😂😂😂😂' and '😂😂' are one reaction.
    Deterministic, no model, no randomness.
    """
    t = unicodedata.normalize("NFKC", text or "").casefold()
    t = _strip_punctuation(t)
    t = re.sub(r"\s+", " ", t).strip()
    t = _CHAR_RUN.sub(r"\1\1", t)
    t = _NGRAM_RUN.sub(r"\1\1", t)
    t = _EMOTE_RUN.sub(r"\1", t)
    return t


@dataclass(slots=True)
class Burst:
    key: str
    sample: str
    count: int
    first_ts_ms: int
    last_ts_ms: int
    event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "key": self.key, "sample": self.sample, "count": self.count,
            "first_ts_ms": self.first_ts_ms, "last_ts_ms": self.last_ts_ms,
            "event_ids": self.event_ids,
        }


def reduce_chat(events: Iterable[Event], *, keep_ids: int = 5) -> List[Burst]:
    """Group chat events by canonical form. Order is deterministic: first appearance.

    `keep_ids` bounds how many source ids each burst carries into the prompt - enough for the
    provenance gate to verify, few enough to keep the prompt small.
    """
    bursts: Dict[str, Burst] = {}
    for e in events:
        if e.type != "chat_message":
            continue
        # A message that canonicalises to nothing is punctuation only. It used to be dropped
        # here, so burst counts did not sum to the messages in the window and the volume simply
        # disappeared. It is now a bucket of its own: contentless, but counted.
        key = canonical(e.text) or EMPTY_KEY
        b = bursts.get(key)
        if b is None:
            bursts[key] = Burst(key=key,
                                sample=e.text if key != EMPTY_KEY else EMPTY_SAMPLE, count=1,
                                first_ts_ms=e.ts_ms, last_ts_ms=e.ts_ms,
                                event_ids=[e.event_id])
        else:
            b.count += 1
            b.last_ts_ms = e.ts_ms
            if len(b.event_ids) < keep_ids:
                b.event_ids.append(e.event_id)
    return list(bursts.values())


def compression_ratio(events: List[Event], bursts: List[Burst]) -> float:
    n = sum(1 for e in events if e.type == "chat_message")
    return (len(bursts) / n) if n else 1.0
