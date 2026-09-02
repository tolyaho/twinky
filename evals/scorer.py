"""Scoring.

Two primary metrics, both legible in five seconds:

  A. trigger accuracy      of the cards that MATCH a gold signal, the fraction naming the
                           correct causing event OR correctly returning "unknown".
                           The denominator is matched cards, not every card emitted: gold is not
                           exhaustive on 12 cases, so a real signal nobody labelled would
                           otherwise be scored as a wrong trigger. That makes the metric
                           un-lowerable by noise on its own, so it is always read next to
                           `unmatched_rate` below.
  A2. unmatched rate       the fraction of emitted cards matching no gold signal. Without it a
                           system could emit one correct card and nine hallucinations and still
                           report a trigger accuracy of 1.0 — measured, not hypothetical.
  B. unsupported-card rate the fraction of cards whose evidence fails deterministic validation.
                           NEEDS NO GOLD LABELS, so it runs over every fixture for free.

An earlier plan proposed a composite requiring four simultaneous conditions for a true positive.
On 12 cases that yields near-zero, unstable numbers for both systems and is unreadable in a
five-minute video. Rejected deliberately - see notes/03-EVAL_DESIGN.md.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from ts.events import EventIndex
from ts.provenance import UNKNOWN, check_card


@dataclass
class CaseScore:
    case_id: str
    system: str
    n_cards: int
    n_gold: int
    trigger_correct: int
    trigger_scored: int
    unmatched: int
    unsupported: int
    signal_recall_hits: int
    abstain_expected: bool
    abstain_correct: Optional[bool]
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None

    @property
    def trigger_accuracy(self) -> Optional[float]:
        return (self.trigger_correct / self.trigger_scored) if self.trigger_scored else None

    @property
    def unmatched_rate(self) -> Optional[float]:
        return (self.unmatched / self.n_cards) if self.n_cards else None

    @property
    def unsupported_rate(self) -> Optional[float]:
        return (self.unsupported / self.n_cards) if self.n_cards else None

    @property
    def signal_recall(self) -> Optional[float]:
        return (self.signal_recall_hits / self.n_gold) if self.n_gold else None

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d.update({
            "trigger_accuracy": self.trigger_accuracy,
            "unmatched_rate": self.unmatched_rate,
            "unsupported_rate": self.unsupported_rate,
            "signal_recall": self.signal_recall,
        })
        return d


def _match_gold(card: Dict[str, Any], gold_signals: List[Dict[str, Any]],
                taken: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """A predicted card matches a gold signal when the type agrees and their evidence overlaps.
    Deliberately simple: matching rules must be frozen and explainable.

    Matching is one-to-one. `taken` holds the gold signals already claimed by an earlier card,
    because a gold signal can only be found once: without it, a system emitting the same card
    twice had that one signal weighted twice in trigger accuracy.
    """
    ctype = card.get("type")
    cev = set(card.get("evidence") or [])
    best, best_overlap = None, 0
    for g in gold_signals:
        if g.get("type") != ctype or (taken is not None and id(g) in taken):
            continue
        overlap = len(cev & set(g.get("relevant_message_ids") or []))
        if overlap > best_overlap:
            best, best_overlap = g, overlap
    return best if best_overlap > 0 else None


def score_case(*, case_id: str, system: str, cards: List[Dict[str, Any]],
               gold: Dict[str, Any], index: EventIndex,
               latency_ms: Optional[int] = None, cost_usd: Optional[float] = None) -> CaseScore:
    gold_signals = gold.get("gold_signals") or []
    must_abstain = bool(gold.get("must_abstain"))

    unsupported = sum(0 if check_card(c, index).ok else 1 for c in cards)

    trigger_correct = trigger_scored = unmatched = 0
    matched_gold_ids = set()

    # Emission order, so the assignment is deterministic and a re-run reproduces it exactly.
    for card in cards:
        g = _match_gold(card, gold_signals, taken=matched_gold_ids)
        if g is None:
            unmatched += 1
            continue
        matched_gold_ids.add(id(g))
        trigger_scored += 1
        pred = (card.get("trigger") or {}).get("event_id") or UNKNOWN
        want = g.get("trigger_event_id") or UNKNOWN
        if pred == want:
            trigger_correct += 1

    substantive = [c for c in cards if c.get("type") != "none"]
    abstain_correct = None
    if must_abstain:
        abstain_correct = len(substantive) == 0

    return CaseScore(
        case_id=case_id, system=system, n_cards=len(cards), n_gold=len(gold_signals),
        trigger_correct=trigger_correct, trigger_scored=trigger_scored, unmatched=unmatched,
        unsupported=unsupported, signal_recall_hits=len(matched_gold_ids),
        abstain_expected=must_abstain, abstain_correct=abstain_correct,
        latency_ms=latency_ms, cost_usd=cost_usd,
    )


def aggregate(scores: List[CaseScore]) -> Dict[str, Any]:
    cards = sum(s.n_cards for s in scores)
    scored = sum(s.trigger_scored for s in scores)
    return {
        "cases": len(scores),
        "cards": cards,
        "trigger_accuracy": (sum(s.trigger_correct for s in scores) / scored) if scored else None,
        "unmatched_rate": (sum(s.unmatched for s in scores) / cards) if cards else None,
        "unsupported_rate": (sum(s.unsupported for s in scores) / cards) if cards else None,
        "signal_recall": (
            sum(s.signal_recall_hits for s in scores) / sum(s.n_gold for s in scores)
        ) if sum(s.n_gold for s in scores) else None,
        "abstention_correct": sum(1 for s in scores if s.abstain_correct) or 0,
        "abstention_cases": sum(1 for s in scores if s.abstain_expected),
    }
