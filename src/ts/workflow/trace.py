"""Trajectory writer.

Required deliverable: representative trajectories for every agent used, followable from the
agent instructions through to the final result, showing tool responses, retries, verification
decisions and human checkpoints.

Written as work happens. Reconstructing traces at the end is a qualification-gate risk and
dishonest.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TRACE_DIR = "trajectories/product-agent"


def trace_dir() -> Path:
    """`TS_TRACE_DIR` redirects trajectory output, the same way `TS_LLM_MODE` redirects the cache.

    `trajectories/` is a graded deliverable, so nothing but real runs belongs in it. The test
    suite pointed 55 files at it before this existed, all with case ids like `t3` that no
    evaluation case has.
    """
    return Path(os.getenv("TS_TRACE_DIR") or DEFAULT_TRACE_DIR)


def make_trace_id(agent: str, case_id: str) -> str:
    """Derived from (agent, case_id), never from a uuid or the clock.

    The trace id is copied onto every card and therefore into the result document that
    REPRODUCTION.md tells a judge to diff. A uuid4 made two replays of the same fixture differ
    in a file we publish as reproducible, and left an orphan trajectory behind on every run.
    Re-running now overwrites the trajectory it replaces.
    """
    return "trc_" + hashlib.sha256(f"{agent}|{case_id}".encode("utf-8")).hexdigest()[:8]


class Trace:
    def __init__(self, agent: str, case_id: str, out_dir: Path | str | None = None) -> None:
        self.trace_id = make_trace_id(agent, case_id)
        self.agent = agent
        self.case_id = case_id
        self.out_dir = Path(out_dir) if out_dir is not None else trace_dir()
        self.steps: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {}
        self._t0 = time.perf_counter()
        # Same source of truth as the cache, and for the same reason.
        self._timed = (os.getenv("TS_LLM_MODE") or "replay").lower() != "replay"

    def _elapsed_ms(self) -> Optional[int]:
        """Wall-clock elapsed since the run started, or `None` on a replay.

        This is the `make_trace_id` problem one field over. A uuid4 trace id made two replays of
        the same fixture differ in a file published as reproducible; so did this, because
        `perf_counter` resolves a cached lookup as 0 ms on one run and 1 ms on the next. One
        frozen-case trajectory changed on every `make eval`.

        Timing a replay is also meaningless, which `evidence/report.md` already says in as many
        words: a replay reads cached responses, so it measures disk, not the model. `None` says
        "not measured in this mode" — `0` would be a fabricated measurement, and the steps are
        ordered by position in the list anyway, so nothing is lost.

        In `record` mode the numbers are real latencies against a live provider and are kept:
        45 of the committed trajectories carry them, and they are the only latency data the
        project has.
        """
        if not self._timed:
            return None
        return int((time.perf_counter() - self._t0) * 1000)

    def instructions(self, system: str, user: str) -> None:
        self.steps.append({"kind": "instructions", "system": system, "user": user,
                           "at_ms": self._elapsed_ms()})

    def tool_call(self, name: str, args: Dict[str, Any], result_summary: Any) -> None:
        self.steps.append({"kind": "tool_call", "tool": name, "args": args,
                           "result": result_summary, "at_ms": self._elapsed_ms()})

    def model_call(self, model: str, request_hash: str, cached: bool,
                   tokens: Optional[Dict[str, int]] = None, cost_usd: Optional[float] = None) -> None:
        self.steps.append({"kind": "model_call", "model": model, "request_hash": request_hash,
                           "cached": cached, "tokens": tokens, "cost_usd": cost_usd,
                           "at_ms": self._elapsed_ms()})

    def retry(self, why: str, attempt: int) -> None:
        self.steps.append({"kind": "retry", "why": why, "attempt": attempt, "at_ms": self._elapsed_ms()})

    def gate(self, card_id: str, ok: bool, violations: List[Dict[str, Any]]) -> None:
        self.steps.append({"kind": "provenance_gate", "signal_id": card_id, "ok": ok,
                           "violations": violations, "at_ms": self._elapsed_ms()})

    def human_checkpoint(self, what: str, state: str) -> None:
        """Outward actions stay drafts until a person approves them (ground rule 04)."""
        self.steps.append({"kind": "human_checkpoint", "what": what, "state": state,
                           "at_ms": self._elapsed_ms()})

    def result(self, payload: Any) -> None:
        self.steps.append({"kind": "result", "payload": payload, "at_ms": self._elapsed_ms()})

    def write(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{self.case_id}_{self.trace_id}.json"
        path.write_text(json.dumps({
            "trace_id": self.trace_id, "agent": self.agent, "case_id": self.case_id,
            "meta": self.meta, "duration_ms": self._elapsed_ms(), "steps": self.steps,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        return path
