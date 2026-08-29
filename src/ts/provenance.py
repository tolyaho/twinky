"""Deterministic provenance gate.

Rejects any card whose evidence does not check out. This is both a product feature (abstention
beats a confident invented cause) and primary metric B, which needs no gold labels and therefore
runs over every fixture for free.

The failure mode it targets was observed in the team's own testing, 4 Jan 2026:
"sometimes the clusters don't attach to anything".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .events import EventIndex

UNKNOWN = "unknown"
NONE = "none"   # the explicit "no signal in this window" card
CHAT_MESSAGE = "chat_message"   # the only event type that can serve as evidence


def normalize(text: str) -> str:
    """Casefold, strip accents-insensitively, collapse whitespace and punctuation runs.

    Quote matching must survive transcription punctuation drift without becoming so loose that
    an invented quote passes.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.casefold()
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class GateResult:
    ok: bool
    violations: List[Violation]

    @property
    def codes(self) -> List[str]:
        return [v.code for v in self.violations]


def check_abstention(card: Dict[str, Any]) -> GateResult:
    """A `none` card declares that nothing happened, so there is nothing to verify.

    It used to fail on E_NO_EVIDENCE, because a card with no claim has no citations. That made
    a correct abstention score 1.0 on the unsupported-card rate — perfect behaviour, worst
    possible number on the headline metric — and put it in the dashboard's rejected bin, where
    the demo showed the product's best moment as a failure.

    The only way an abstention can be wrong is by contradicting itself: citing messages or
    naming a cause while declaring that nothing happened.
    """
    v: List[Violation] = []
    if card.get("evidence"):
        v.append(Violation("E_NONE_WITH_EVIDENCE",
                           "a 'none' card cites messages while claiming nothing happened"))
    trigger_id = (card.get("trigger") or {}).get("event_id")
    if trigger_id and trigger_id != UNKNOWN:
        v.append(Violation("E_NONE_WITH_TRIGGER",
                           f"a 'none' card names a cause: {trigger_id}"))
    return GateResult(ok=not v, violations=v)


def check_card(card: Dict[str, Any], index: EventIndex, *, min_quote_ratio: float = 0.6) -> GateResult:
    """Validate one signal card against the event index.

    A `none` card takes the abstention path above; it asserts nothing, so the checks below do
    not apply to it.

    Checks, in order:
      E_NO_EVIDENCE      no representative messages cited
      E_UNKNOWN_MSG      a cited message id does not exist in the fixture
      E_EVIDENCE_NOT_A_MESSAGE  a cited id exists but is a transcript segment or a frame
      E_CIRCULAR_EVIDENCE       the trigger is cited as evidence for the signal it caused
      E_MSG_OUT_WINDOW   a cited message falls outside the card's claimed window,
                         which is half-open [start, end) exactly as `events.window` is
      E_UNKNOWN_TRIGGER  the trigger event id does not exist
      E_TRIGGER_LATE     the trigger occurs after the messages it supposedly caused
      E_QUOTE_MISMATCH   the quoted trigger text is not present in that event's text
    """
    if card.get("type") == NONE:
        return check_abstention(card)

    v: List[Violation] = []

    evidence: List[str] = list(card.get("evidence") or [])
    if not evidence:
        v.append(Violation("E_NO_EVIDENCE", "card cites no representative messages"))

    win = card.get("window_ms")
    w_start, w_end = (int(win[0]), int(win[1])) if win else (None, None)

    evidence_ts: List[int] = []
    for mid in evidence:
        ev = index.get(mid)
        if ev is None:
            v.append(Violation("E_UNKNOWN_MSG", f"{mid} not in fixture"))
            continue
        # Evidence means representative CHAT messages. The gate used to accept any event id, so
        # a card could cite the transcript segment that caused the signal as the audience's
        # response to it, or offer a frame caption as a message, and be verified.
        if ev.type != CHAT_MESSAGE:
            v.append(Violation("E_EVIDENCE_NOT_A_MESSAGE",
                               f"{mid} is a {ev.type}, not a chat message"))
            continue
        evidence_ts.append(ev.ts_ms)
        # Half-open, matching `events.window` exactly. With an inclusive end the gate accepted a
        # card citing a message at the boundary that the agent's own tools never returned for
        # that window — and tiles are adjacent, so the message belonged to the next one. The
        # gate exists to catch precisely that claim, and it was blind to it.
        if w_start is not None and not (w_start <= ev.ts_ms < w_end):
            v.append(Violation("E_MSG_OUT_WINDOW",
                               f"{mid} at {ev.ts_ms} outside [{w_start},{w_end})"))

    trigger = card.get("trigger") or {}
    tid = trigger.get("event_id")

    if tid and tid != UNKNOWN:
        if tid in evidence:
            v.append(Violation("E_CIRCULAR_EVIDENCE",
                               f"{tid} is cited as evidence for the signal it supposedly caused"))
        tev = index.get(tid)
        if tev is None:
            v.append(Violation("E_UNKNOWN_TRIGGER", f"{tid} not in fixture"))
        else:
            if evidence_ts and tev.ts_ms > min(evidence_ts):
                v.append(Violation(
                    "E_TRIGGER_LATE",
                    f"trigger {tid} at {tev.ts_ms} is after earliest cited message {min(evidence_ts)}",
                ))
            quote = trigger.get("quote")
            if quote:
                nq, nt = normalize(quote), normalize(tev.text)
                if nq and nq not in nt and _token_overlap(nq, nt) < min_quote_ratio:
                    v.append(Violation("E_QUOTE_MISMATCH", f"quote not found in {tid}: {quote!r}"))

    return GateResult(ok=not v, violations=v)


def _token_overlap(a: str, b: str) -> float:
    ta, tb = a.split(), set(b.split())
    if not ta:
        return 0.0
    return sum(1 for t in ta if t in tb) / len(ta)


def apply_gate(cards: List[Dict[str, Any]], index: EventIndex) -> Dict[str, Any]:
    """Partition cards into verified and rejected. Rejected cards are kept, not deleted -
    they are the evidence behind metric B and belong in the trace."""
    verified, rejected = [], []
    for card in cards:
        res = check_card(card, index)
        record = dict(card)
        record["gate"] = {"ok": res.ok, "violations": [asdict(vv) for vv in res.violations]}
        if res.ok:
            # A passing `none` card is an abstention, not a verified signal. Saying so in the
            # document keeps the vocabulary the dashboard and the debrief already use.
            default = "abstained" if card.get("type") == NONE else "verified"
            record["status"] = record.get("status") or default
            verified.append(record)
        else:
            record["status"] = "rejected"
            rejected.append(record)
    total = len(cards)
    return {
        "verified": verified,
        "rejected": rejected,
        "unsupported_rate": (len(rejected) / total) if total else 0.0,
        "total": total,
    }
