"""Content-addressed model-call cache.

This is the reproducibility mechanism. Judges must be able to run the baseline, the agent and
the evaluation with NO API keys and zero cost, and get byte-identical numbers.

Modes (env `TS_LLM_MODE`):
  replay  (default)  cache hit required; a MISS RAISES. Never a silent API call.
  record             call the provider, write through to the cache.
  live                call the provider, do not read or write the cache.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DEFAULT_CACHE_DIR = Path("cache/llm")


class CacheMiss(RuntimeError):
    """Raised in replay mode. Loud by design: a silent API call would break reproduction."""


def request_hash(request: Dict[str, Any]) -> str:
    """Stable hash over the full request. Key order must not matter."""
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR, mode: Optional[str] = None) -> None:
        self.dir = Path(cache_dir)
        self.mode = (mode or os.getenv("TS_LLM_MODE") or "replay").lower()
        if self.mode not in {"replay", "record", "live"}:
            raise ValueError(f"unknown TS_LLM_MODE: {self.mode!r}")
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, key: str, request: Dict[str, Any], response: Dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"request": request, "response": response},
                       sort_keys=True, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def call(self, request: Dict[str, Any], provider: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Single entry point for every model call in the system."""
        key = request_hash(request)

        if self.mode == "live":
            return provider(request)

        entry = self.get(key)
        if entry is not None:
            self.hits += 1
            return entry["response"]

        self.misses += 1
        if self.mode == "replay":
            raise CacheMiss(
                f"no cached response for {key[:12]}... in replay mode.\n"
                f"model={request.get('model')!r} temperature={request.get('temperature')!r}\n"
                "A miss means the request changed. Either a prompt/model/temperature was edited, "
                "or a non-deterministic value (wall-clock time, unseeded random, unstable batch "
                "composition) leaked into the request. Fix the determinism, or re-record with "
                "TS_LLM_MODE=record."
            )

        response = provider(request)
        self.put(key, request, response)
        return response

    def stats(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}
