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

import os

import json
from typing import Any, Callable, Dict, List, Optional

from ..cache import ResponseCache, request_hash
from ..events import EventIndex
from ..provenance import apply_gate
from ..providers.base import build_request, extract_content
from ..workflow.agent import CARD_CONTRACT, INTRO, cap_cards
from ..workflow.trace import Trace


DEFAULT_TEXT_MODEL = os.getenv("TS_TEXT_MODEL") or "deepseek-v4-flash"

# The baseline used to be handed the AGENT's system prompt, which specifies a tool-calling
# protocol. Having no tools, the model did the only correct thing and replied
# {"action": "call_tools", ...}; `.get("cards", [])` then returned [] and the run reported a
# clean zero. Across eleven cases the baseline emitted no cards at all and the eval printed it
# as a result, so there was nothing to compare the agent against.
#
# The contract below is byte-identical to the agent's - same schema, same rules, same cap. The
# only difference is how an answer is reached, which is the difference under measurement.
SYSTEM = INTRO + """

You see the whole window at once. There are no tools and no further steps.
Reply with ONLY a JSON object: {"cards": [...]}

Each line of the input is one event, tagged CHAT, SPEECH or SCREEN, and carries the id you must
cite for it. """ + CARD_CONTRACT


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
        chat_only: bool = False, model: str = DEFAULT_TEXT_MODEL,
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
    parse_error = None
    cards: List[Dict[str, Any]] = []
    try:
        payload = json.loads(extract_content(resp))
        if not isinstance(payload, dict) or "cards" not in payload:
            # A reply that parses but carries no `cards` key is a protocol failure, not an empty
            # result. Treating the two the same is what let eleven cases report a clean zero.
            shape = (",".join(sorted(payload)[:4]) if isinstance(payload, dict)
                     else type(payload).__name__)
            raise ValueError(f"reply has no 'cards' key (got: {shape})")
        # The same cap the agent gets. The eval promises both systems an identical output schema
        # and card cap; enforcing it in one place is what makes that true rather than hoped for.
        cards, dropped = cap_cards(payload.get("cards") or [])
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)
        trace.retry(f"unparseable response: {exc}", 1)

    for i, c in enumerate(cards):
        c.setdefault("signal_id", f"sig_{case_id}_b{i:02d}")
        c["window_ms"] = [start_ms, end_ms]
        c["trace_id"] = trace.trace_id

    out = apply_gate(cards, index)
    for c in out["verified"] + out["rejected"]:
        trace.gate(c["signal_id"], c["gate"]["ok"], c["gate"]["violations"])
    out["trace_id"] = trace.trace_id
    out["cards_dropped_by_cap"] = dropped
    out["parse_error"] = parse_error
    trace.result({"verified": len(out["verified"]), "rejected": len(out["rejected"]),
                  "cards_dropped_by_cap": dropped, "parse_error": parse_error})
    out["trace_path"] = str(trace.write())
    return out
