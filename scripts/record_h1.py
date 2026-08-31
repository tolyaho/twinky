"""Record and measure item H1 — the agent's chat tool pointed at `group_chat`.

One command between a diagnosis and a number. It records the AGENT ARM ONLY, into a temporary
evidence directory and a temporary trajectory directory, prints the comparison against the adopt
criteria, and writes nothing a judge reads. Adopting is a separate, deliberate step.

    git apply experiments/h1-group-chat.patch
    python scripts/record_h1.py

Needs a key. Everything else in this repository does not, and that stays true: this script is not
on the graded path, is not imported by anything, and `make eval` continues to reproduce the
published numbers from the committed cache with no credentials at all.

Three safety properties, all enforced here rather than trusted:

1. **The frozen systems cannot be re-recorded.** `record` mode reads the cache before it calls a
   provider, and the patch touches only `Tools.group_repeated` and `TOOLS_DOC`, which the baseline
   does not import. The script proves it by running baseline and ablation in `replay` first, where
   a miss raises, and refuses to continue unless every one is a hit.
2. **The model names stay unset.** `.env` assigns `TS_TEXT_MODEL` twice — `deepseek-v4-flash` and
   then `gpt-4.1-nano` — and `.env.example` documents that setting them at all turns every
   committed entry into a miss. Only the key and the base URL are taken from that file.
3. **Nothing a judge reads is touched.** Evidence goes to a temp directory, trajectories go to a
   temp directory. The only durable write is new entries in `cache/llm/`, which is the recording.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADOPT_TRIGGER_ACCURACY = 0.500      # the published agent's figure; H1 must not go backwards
BASE_URL = "https://api.openai.com/v1"


def key_from_env_file() -> str:
    """The recording key, from `.env`, never printed and never logged."""
    path = REPO / ".env"
    if not path.is_file():
        sys.exit("no .env; export TS_LLM_API_KEY instead and re-run")
    values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                  if re.match(r"^[A-Z_]+=", line))
    for name in ("TS_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        if values.get(name, "").strip():
            return values[name].strip()
    sys.exit("no usable key in .env")


def prove_the_frozen_systems_are_untouched() -> None:
    """Baseline and ablation in replay, where a miss raises. Any miss means STOP."""
    from evals.run_eval import FIXTURES_DIR, load_cases
    from ts.baseline import single_prompt
    from ts.cache import ResponseCache
    from ts.ingest.replay import load_fixture

    cache = ResponseCache(mode="replay")
    for case in load_cases("all"):
        index = load_fixture(FIXTURES_DIR / case["fixture"])
        start_ms, end_ms = case["window_ms"]
        single_prompt.run(index, cache, case["case_id"], start_ms, end_ms)
        single_prompt.run(index, cache, case["case_id"], start_ms, end_ms, chat_only=True)
    stats = cache.stats()
    if stats["misses"]:
        sys.exit(f"REFUSING TO RECORD: {stats['misses']} baseline/ablation miss(es). Their "
                 f"numbers are frozen and recording over them destroys the comparison.")
    print(f"  frozen systems verified unchanged: {stats['hits']} hits, 0 misses")


def main() -> int:
    os.chdir(REPO)
    sys.path.insert(0, str(REPO / "src"))

    print("H1 — group_repeated -> group_chat\n")
    print("checking nothing frozen is about to move…")
    os.environ["TS_LLM_MODE"] = "replay"
    prove_the_frozen_systems_are_untouched()

    out = Path(tempfile.mkdtemp(prefix="h1-evidence-"))
    traces = Path(tempfile.mkdtemp(prefix="h1-traj-"))
    os.environ.update({"TS_LLM_MODE": "record", "TS_LLM_API_KEY": key_from_env_file(),
                       "TS_LLM_BASE_URL": BASE_URL, "TS_TRACE_DIR": str(traces)})
    for stale in ("TS_TEXT_MODEL", "TS_VISION_MODEL"):
        os.environ.pop(stale, None)

    print(f"\nrecording the agent arm; evidence -> {out}\n")
    from evals.run_eval import main as run_eval
    code = run_eval(["--ablation", "--out", str(out)])
    if code != 0:
        print(f"\neval exited {code} — nothing to compare. The tree is unchanged apart from "
              f"cache entries; `git checkout -- src/ts/workflow/ cache/llm/` reverts.")
        return code

    print("\n" + "=" * 78)
    compare(out)
    return 0


def compare(out: Path) -> None:
    """Before and after, on the three things that decide it."""
    import collections
    import json

    def census(path: Path):
        rows = json.loads(path.read_text(encoding="utf-8"))
        agent = [r for r in rows if r["system"] == "agent"]
        source, codes, abstained = collections.Counter(), collections.Counter(), 0
        for run in agent:
            for card in run["cards"]:
                if card.get("status") == "abstained":
                    abstained += 1
                    source["abstained"] += 1
                else:
                    trigger = card.get("trigger") or {}
                    kind, event_id = trigger.get("kind"), trigger.get("event_id")
                    source["unknown" if kind == "unknown" or event_id in (None, "unknown")
                           else str(kind)] += 1
                for violation in (card.get("gate") or {}).get("violations") or []:
                    codes[violation if isinstance(violation, str)
                          else violation.get("code")] += 1
        return source, codes, abstained

    before = census(REPO / "evidence/predictions.json")
    after = census(out / "predictions.json")

    print("trigger source (agent cards)")
    for name in sorted(set(before[0]) | set(after[0])):
        print(f"  {name:16s} {before[0][name]:4d}  ->  {after[0][name]:4d}")
    print("\nE_ census (agent cards)")
    for name in sorted(set(before[1]) | set(after[1])):
        print(f"  {name:26s} {before[1][name]:4d}  ->  {after[1][name]:4d}")

    print(f"\nabstentions: {before[2]}  ->  {after[2]}")
    print(f"\nADOPT ONLY IF trigger accuracy >= {ADOPT_TRIGGER_ACCURACY:.3f} "
          f"AND abstentions > 0.")
    if after[2] == 0:
        print("  abstentions are ZERO. That is Removed experiment #2 under a new name. REVERT.")
    print(f"\nTrigger accuracy is in {out}/report.md — read it before deciding, and write the "
          f"result up either way.\nRevert with: git checkout -- src/ts/workflow/ cache/llm/")


if __name__ == "__main__":
    raise SystemExit(main())
