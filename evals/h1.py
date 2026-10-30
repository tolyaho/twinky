"""Replay the rejected H1 grouping arm without editing the shipped agent or old results.

python -m evals.h1 --out .runtime/h1-reaction-v2
The historical strict-v1 results remain in evidence/h1/.
"""
import sys
from contextlib import contextmanager
from unittest.mock import patch
from ts.workflow import agent, tools
from ts.workflow.reduce import group_chat
from evals import run_eval

OLD = "  group_repeated(start_ms, end_ms)        chat, deduplicated into bursts with counts and ids"
NEW = """  group_repeated(start_ms, end_ms)        chat grouped into what the room is SAYING, not into
                                          identical strings. Each group has `label` (what it is
                                          about), `count`, `samples` (verbatim messages) and
                                          `event_ids` (every message in it). Cite ids from
                                          `event_ids` - `key` and `label` are not ids."""

def grouped(self, start_ms, end_ms):
    self._guard(start_ms, end_ms)
    groups = group_chat(self.index.window(start_ms, end_ms, types=["chat_message"]))
    self.calls.append({"tool": "group_repeated", "args": {"start_ms": start_ms, "end_ms": end_ms},
                       "n": len(groups)})
    return [g.to_dict() for g in groups]

@contextmanager
def arm():
    with patch.object(agent, "SYSTEM", agent.SYSTEM.replace(OLD, NEW)), \
         patch.object(tools.Tools, "group_repeated", grouped):
        yield

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--out" not in argv:
        argv += ["--out", ".runtime/h1-reaction-v2"]
    with arm():
        return run_eval.main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
