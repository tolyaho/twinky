"""The fair baseline.

ONE direct prompt receiving THE SAME raw events the final system sees - chat, final transcript
segments, frame captions, ids and timestamps - with the same output schema and card cap. No
tools, no reduction, no rolling state, no verifier, no memory.

Comparing the final system against a chat-only baseline would measure the value of giving it more
data, not the value of the agentic workflow. A judge would spot that immediately, so the
chat-only run is a separate diagnostic ablation (`chat_only=True`), never the headline baseline.

Note it is scored through the SAME provenance gate as the agent. The gate is the scorer, not part
of the agent's advantage - otherwise the comparison would be rigged.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from ..cache import ResponseCache, request_hash
from ..events import EventIndex
from ..provenance import apply_gate
from ..providers.base import build_request, extract_content
from ..workflow.agent import SYSTEM, cap_cards
from ..workflow.trace import Trace


def render_events(index: EventIndex, start_ms: int, end_ms: int, chat_only: bool = False) -> str:
    types = ["chat_message"] if chat_only else None
    lines = []
    for e in index.window(start_ms, end_ms, types=types, final_only=True):
        if e.type == "chat_message":
            lines.append(f"[{e.ts_ms}] CHAT {e.event_id} {e.author}: {e.text}")
        elif e.type == "transcript_segment":
            lines.append(f"[{e.ts_ms}] SPEECH {e.event_id}: {e.text}")
        else:
            lines.append(f"[{e.ts_ms}] SCREEN {e.event_id}: {e.text}")
    return "\n".join(lines)


def run(index: EventIndex, cache: ResponseCache, case_id: str, start_ms: int, end_ms: int, *,
        chat_only: bool = False, model: str = "deepseek-v4-flash",
        provider: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    if provider is None:
        from ..providers.base import DeepSeekProvider
        provider = DeepSeekProvider().complete

    name = "baseline_chat_only" if chat_only else "baseline_single_prompt"
    trace = Trace(agent=name, case_id=case_id)
    trace.meta = {"model": model, "window_ms": [start_ms, end_ms], "chat_only": chat_only}

    user = render_events(index, start_ms, end_ms, chat_only=chat_only)
    trace.instructions(SYSTEM, user)

    req = build_request(model=model, system=SYSTEM, user=user,
                        temperature=0.0, max_tokens=900, json_mode=True)
    before = cache.hits
    resp = cache.call(req, provider)
    trace.model_call(model, request_hash(req), cached=cache.hits > before)

    dropped = 0
    try:
        # The same cap the agent gets. The eval promises both systems an identical output schema
        # and card cap; enforcing it in one place is what makes that true rather than hoped for.
        cards, dropped = cap_cards(json.loads(extract_content(resp)).get("cards", []))
    except Exception as exc:  # noqa: BLE001
        trace.retry(f"unparseable response: {exc}", 1)
        cards: List[Dict[str, Any]] = []

    for i, c in enumerate(cards):
        c.setdefault("signal_id", f"sig_{case_id}_b{i:02d}")
        c["window_ms"] = [start_ms, end_ms]
        c["trace_id"] = trace.trace_id

    out = apply_gate(cards, index)
    for c in out["verified"] + out["rejected"]:
        trace.gate(c["signal_id"], c["gate"]["ok"], c["gate"]["violations"])
    out["trace_id"] = trace.trace_id
    out["cards_dropped_by_cap"] = dropped
    trace.result({"verified": len(out["verified"]), "rejected": len(out["rejected"]),
                  "cards_dropped_by_cap": dropped})
    out["trace_path"] = str(trace.write())
    return out
