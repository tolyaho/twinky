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


# ---------------------------------------------------------------------------
# Grouping: the same job one level up.
#
# `reduce_chat` groups by exact canonical equality, which is the wrong unit for an audience
# signal. Twenty people brute-forcing an on-screen word puzzle type twenty different strings, so
# exact matching splits one signal into twenty rows of one and the board renders "Audience
# mentions 'dracula'" twenty times, each with `Evidence - 1 message`. One message is not evidence
# of an audience reaction; it is a message.
#
# Three deterministic rules, no model, no cost, applied in order. A message lands in exactly one
# group, so counts still sum and nothing is counted twice.
#
# `reduce_chat` is deliberately left alone. Its output is rendered into the agent's prompt and
# therefore hashed into every recorded model call - rewriting it would miss the cache on every
# frozen case and take keyless replay down with it. Grouping is additive and read by the report,
# not by the agent.
# ---------------------------------------------------------------------------

REACTION_KEY = "∎reaction"
REACTION_LABEL = "reaction wave"

# Laughter, spelled the handful of ways it is actually spelled, after `canonical` has already
# folded the repeats ("AHAHAHAHA" -> "ahaha"). Anchored: "lol" inside a sentence is not a
# reaction, it is a sentence.
_LAUGHTER = re.compile(
    r"^(?:"
    r"l+o+l+(?:ol)*|lmf?ao|rofl|kekw?|xd+|"
    r"(?:a?ha){2,}h?|(?:he){2,}|"             # haha, ahaha, hahaha, hehe
    r"(?:а?ха){2,}х?|(?:хе){2,}"              # ахаха, хаха, хехе
    r")$",
    flags=re.UNICODE,
)
_WORDISH = re.compile(r"[0-9A-Za-zÀ-ɏЀ-ӿ]", flags=re.UNICODE)

# Deliberately small and frozen. A long list starts encoding opinions about which words carry
# meaning on Twitch, and this rule has to be defensible without a model behind it.
STOPWORDS = frozenset("""
a an and are as at be been but by can cant did do does dont for from get got had has have he her
him his how i if in is it its just like me my no not now of on one or our out she should so some
than that the their them then there these they this to too up us very was we were what when where
which who why will with would you your yours yeah yes yep nah nope ok okay omg pls plz thanks
bro bruh man dude guys chat stream streamer twitch
""".split())

MIN_PREFIX_LEN = 4          # the prefix a single-word message is bucketed by
MIN_PREFIX_GROUP = 4        # a prefix is a signal at four messages, not two
MIN_TOKEN_GROUP = 3         # a shared rare token is a signal at three


@dataclass(slots=True)
class Group:
    """One audience signal: a set of messages that are saying the same thing.

    `count` and `event_ids` are load-bearing - the board cites them and the feed highlights
    them - so they are produced by the rules and never edited afterwards. `label` is display
    only.
    """
    key: str
    rule: str                                   # reaction | prefix | token
    label: str
    count: int
    first_ts_ms: int
    last_ts_ms: int
    event_ids: List[str] = field(default_factory=list)
    samples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "key": self.key, "rule": self.rule, "label": self.label, "count": self.count,
            "first_ts_ms": self.first_ts_ms, "last_ts_ms": self.last_ts_ms,
            "event_ids": self.event_ids, "samples": self.samples,
        }


def is_reaction(canon: str) -> bool:
    """Laughter or symbols only. Both are real audience volume and neither is a topic.

    Left in its own bucket they dominate every ranking - `LOL` x 28 sat at the top of a marlon
    window while the thing chat was actually reacting to sat below the fold.
    """
    if not canon or canon == EMPTY_KEY:
        return False
    if _LAUGHTER.match(canon.replace(" ", "")):
        return True
    return not _WORDISH.search(canon)           # emote-only: symbols, no letters or digits


def _tokens(canon: str) -> List[str]:
    return [t for t in canon.split() if len(t) >= 3 and t not in STOPWORDS]


def _pick(candidates: Dict[str, int], keys: Iterable[str]) -> str:
    """The largest candidate group, ties broken lexicographically.

    A message joins one group only, and which one has to be a function of the data rather than of
    dict ordering, or two runs over the same window disagree.
    """
    return sorted(keys, key=lambda k: (-candidates[k], k))[0]


def group_chat(events: Iterable[Event], *, max_samples: int = 3) -> List[Group]:
    """Group chat into audience signals. Deterministic, free, no model.

    Order of application matters and is the spec:

      1. reaction wave  - laughter and emote-only, one counted bucket
      2. rule B, prefix - single-word messages >=4 chars share their first 4 characters
      3. rule A, token  - what is left shares a content token

    Rule B before rule A because a word-guessing stream is single words, and tokenising them
    first scatters `parab parac parad` across three groups of one. Measured on the recorded
    fixtures, this is the difference between the board showing one row and twenty.

    Returns groups ranked by count. Messages that join nothing are not returned - they are
    singletons, and the caller reports how many were left out rather than pretending they are
    signals.
    """
    msgs = [e for e in events if e.type == "chat_message"]
    canon = {e.event_id: (canonical(e.text) or EMPTY_KEY) for e in msgs}

    # Keys are namespaced by rule. Without it a 4-character token and a prefix bucket - `jump`
    # from "JUMP IN" and `jump` from "JUMPP" - are the same dict key with two different rules,
    # and whichever runs second silently relabels the other.
    assigned: Dict[str, str] = {}               # event_id -> group key
    rules: Dict[str, str] = {}                  # group key -> rule name

    # 1. reaction wave
    for e in msgs:
        if is_reaction(canon[e.event_id]):
            assigned[e.event_id] = REACTION_KEY
            rules[REACTION_KEY] = "reaction"

    # 2. rule B - single-word prefix
    prefix_of: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for e in msgs:
        if e.event_id in assigned:
            continue
        c = canon[e.event_id]
        if " " in c or len(c) < MIN_PREFIX_LEN or not _WORDISH.search(c):
            continue
        p = "p:" + c[:MIN_PREFIX_LEN]
        prefix_of[e.event_id] = p
        counts[p] = counts.get(p, 0) + 1
    for eid, p in prefix_of.items():
        if counts[p] >= MIN_PREFIX_GROUP:
            assigned[eid] = p
            rules[p] = "prefix"

    # 3. rule A - shared content token, on what is left
    token_of: Dict[str, List[str]] = {}
    tcounts: Dict[str, int] = {}
    for e in msgs:
        if e.event_id in assigned:
            continue
        toks = sorted({"t:" + t for t in _tokens(canon[e.event_id])})
        if not toks:
            continue
        token_of[e.event_id] = toks
        for t in toks:
            tcounts[t] = tcounts.get(t, 0) + 1
    # Candidate counts are read once, before any message is placed, so placing a message can
    # never change where the next one goes. One pass, no cascade, no ordering dependence.
    survivors = {t: n for t, n in tcounts.items() if n >= MIN_TOKEN_GROUP}
    for eid, toks in token_of.items():
        live = [t for t in toks if t in survivors]
        if live:
            assigned[eid] = _pick(survivors, live)
            rules[assigned[eid]] = "token"

    final: Dict[str, int] = {}
    for key in assigned.values():
        final[key] = final.get(key, 0) + 1

    # 4. fold a prefix bucket into the word it is the prefix of.
    #
    # Rule B runs first, so on the marlon window where chat identifies an adult performer on
    # screen the single-word "VIOLET" messages land in `viol…` and the sentences - "is that
    # violet", "VIOLET MY GOAT" - land in `violet`. Measured: 8 and 19. That is one signal drawn
    # as two rows, which is the bug this whole function exists to fix, so the prefix bucket is
    # merged into the longer word and the row reads `violet x 27`.
    merged: Dict[str, str] = {}
    for pkey in [k for k in final if rules[k] == "prefix"]:
        body = pkey[2:]
        cand = [t for t in final if rules[t] == "token" and t[2:].startswith(body)]
        if cand:
            merged[pkey] = _pick(final, cand)
    for eid, key in list(assigned.items()):
        if key in merged:
            assigned[eid] = merged[key]
    final = {}
    for key in assigned.values():
        final[key] = final.get(key, 0) + 1

    # A group can fall under its threshold once each message has gone to its single best group.
    # Below threshold it is not a signal, so it is dropped rather than shown.
    floor = {"reaction": 1, "prefix": MIN_PREFIX_GROUP, "token": MIN_TOKEN_GROUP}
    kept = {k for k, n in final.items() if n >= floor[rules[k]]}

    groups: Dict[str, Group] = {}
    for e in msgs:                              # in (ts_ms, event_id) order, as given
        key = assigned.get(e.event_id)
        if key is None or key not in kept:
            continue
        g = groups.get(key)
        if g is None:
            label = REACTION_LABEL if key == REACTION_KEY else (
                f"{key[2:]}…" if rules[key] == "prefix" else key[2:])
            g = groups[key] = Group(key=key, rule=rules[key], label=label, count=0,
                                    first_ts_ms=e.ts_ms, last_ts_ms=e.ts_ms)
        g.count += 1
        g.last_ts_ms = e.ts_ms
        g.event_ids.append(e.event_id)
        if len(g.samples) < max_samples and e.text not in g.samples:
            g.samples.append(e.text)            # verbatim, never the canonical form

    return sorted(groups.values(), key=lambda g: (-g.count, g.first_ts_ms, g.key))


def grouped_summary(events: Iterable[Event], groups: List[Group]) -> Dict[str, int]:
    """`N messages -> M rows -> K singletons`, the footer line the board owes the reader.

    A board that shows six rows out of 1288 messages has to say what happened to the other
    thousand, or six rows read as the whole window.
    """
    msgs = [e for e in events if e.type == "chat_message"]
    grouped = sum(g.count for g in groups)
    return {"messages": len(msgs), "groups": len(groups), "grouped": grouped,
            "ungrouped": len(msgs) - grouped}
