"""Arm C — embedding clustering, as a measured arm rather than as the answer.

The team ran this twice, in October 2025 and March 2026, and recorded the same finding both
times: *"it splits into 100 clusters, but they're all different… with not-great accuracy."*
`notes/01-PRODUCT.md` has it written down twice. So this is not being re-added as a fix. It is
being measured against the same frozen labels as arms A and B, so that a remembered result
becomes a reproducible one — or is overturned.

**Arm C is given every advantage the other two were denied.** A and B were written before the
labels existed and were scored once, at whatever they do. C has one free parameter, the cosine
threshold at which two messages count as the same intent, and the honest way to handle it is not
to pick a number and hope: the whole sweep is reported, and C is credited with its **best**
threshold. If it still loses under those conditions, the conclusion is worth something. If it only
wins at a threshold chosen by looking at the labels, that is tuning on the test set and the write-
up says so in those words.

One batched embeddings call per window, content-addressed like every other call, so the result
replays with no key and no cost.
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Sequence, Tuple

from ts.cache import ResponseCache
from ts.events import Event

MODEL = "text-embedding-3-small"
# The sweep. Reported in full — no single value is presented as "the" threshold, because there is
# no principled way to choose one without looking at the answers.
THRESHOLDS: Tuple[float, ...] = (0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80)


def _provider(request: Dict[str, Any]) -> Dict[str, Any]:
    import httpx

    base = (os.getenv("TS_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = os.getenv("TS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("no key set; embeddings are record-mode only")
    r = httpx.post(f"{base}/embeddings", headers={"Authorization": f"Bearer {key}"},
                   json=request, timeout=120.0)
    r.raise_for_status()
    return r.json()


def embed(chat: Sequence[Event], cache: ResponseCache) -> List[List[float]]:
    """One call for the window. Raises on a replay miss, which is correct here — unlike a
    cosmetic label, a missing embedding means the arm cannot be scored at all, and silently
    scoring zero would look like a measurement."""
    request = {"model": MODEL, "input": [e.text for e in chat]}
    response = cache.call(request, _provider)
    return [row["embedding"] for row in response["data"]]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def cluster(chat: Sequence[Event], vectors: Sequence[Sequence[float]],
            threshold: float) -> Dict[str, str]:
    """Single-link agglomeration at `threshold`, by union-find.

    Deterministic: messages are joined in `(ts_ms, event_id)` order, which is the order the index
    already guarantees, so two runs over the same window agree exactly.
    """
    parent = list(range(len(chat)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(chat)):
        for j in range(i + 1, len(chat)):
            if _cosine(vectors[i], vectors[j]) >= threshold:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)

    return {e.event_id: f"c{find(i)}" for i, e in enumerate(chat)}


def arm(threshold: float, cache: ResponseCache):
    """An arm callable with the same shape as `arm_exact` and `arm_token_prefix`."""
    def run(chat: Sequence[Event]) -> Dict[str, str]:
        return cluster(chat, embed(chat, cache), threshold)
    return run
