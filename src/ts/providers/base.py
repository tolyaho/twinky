"""Provider adapters.

Models sit behind an interface on purpose: if one fails schema compliance on the eval, swap the
model rather than bending the product around it.

Model names as of 2026-08 (verify at api-docs.deepseek.com before quoting in any document):
    deepseek-v4-flash              text, JSON, tool calls. TEXT ONLY.
    deepseek-v4-pro                stronger, for escalation only if the eval justifies the cost
    deepseek-v4-flash-vision-exp   multimodal
`deepseek-chat` and `deepseek-reasoner` were RETIRED 2026-07-24. Never use them.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Protocol


class TextProvider(Protocol):
    def complete(self, request: Dict[str, Any]) -> Dict[str, Any]: ...


def build_chat_request(*, model: str, messages: list, temperature: float = 0.0,
                       max_tokens: int = 900, json_mode: bool = True) -> Dict[str, Any]:
    """Canonical request shape. This dict IS the cache key - keep it stable and free of
    anything non-deterministic (no timestamps, no run ids, no unseeded values).

    Multi-turn: each step of an agent loop hashes to its own cache entry, so a whole
    tool-calling trajectory replays deterministically.
    """
    req: Dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }
    if json_mode:
        req["response_format"] = {"type": "json_object"}
    return req


def build_request(*, model: str, system: str, user: str,
                  temperature: float = 0.0, max_tokens: int = 900,
                  json_mode: bool = True) -> Dict[str, Any]:
    """Single-turn convenience wrapper (used by the baseline)."""
    return build_chat_request(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
    )


class DeepSeekProvider:
    """Live/record mode only. Never called in replay."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        # Endpoint and key come from the environment so the provider can be swapped without a
        # code change - the adapter exists precisely so a failing model is replaced, not
        # worked around. TS_LLM_* win; the DeepSeek names remain as fallbacks.
        self.base_url = (
            base_url or os.getenv("TS_LLM_BASE_URL") or "https://api.deepseek.com/v1"
        ).rstrip("/")
        self.api_key = (
            api_key or os.getenv("TS_LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        )

    def complete(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is unset. The graded path never needs it - "
                "run with TS_LLM_MODE=replay."
            )
        import httpx  # imported lazily so replay-mode runs need no network stack
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request, timeout=120.0,
        )
        r.raise_for_status()
        return r.json()


def extract_content(response: Dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"unexpected provider response shape: {exc}") from exc
