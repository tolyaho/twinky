#!/usr/bin/env bash
# Overnight loop for the ts hackathon build.
#   bash run-night.sh            # run it
#   touch STOP                   # stop it after the current iteration
#
# Design: FRESH session every iteration. State lives in PROGRESS.md / DECISIONS.md /
# COST_LEDGER.md, not in conversation context. That is cheaper and cannot bloat.

set -uo pipefail

PROJECT="$HOME/Desktop/personal/micro1/ts"
PROMPT="$HOME/Desktop/personal/micro1/NIGHT_LOOP.md"
LOGS="$PROJECT/.nightlogs"
INTERVAL="${INTERVAL:-1800}"        # 30 min
MAX_ITER="${MAX_ITER:-16}"          # 16 x 30min = 8h. Hard stop.
STOP_AT="${STOP_AT:-09:00}"         # wall-clock stop
MODEL="${MODEL:-sonnet}"            # cheaper than opus for mechanical work

cd "$PROJECT" || { echo "no such dir: $PROJECT"; exit 1; }
mkdir -p "$LOGS"
[ -f "$PROMPT" ] || { echo "no prompt at $PROMPT"; exit 1; }

echo "== preflight =="
make test >/dev/null 2>&1 && echo "tests green" || { echo "TESTS ARE RED - fix before looping"; exit 1; }
echo "prompt: $PROMPT ($(wc -l < "$PROMPT") lines)"
echo "interval: ${INTERVAL}s | max iterations: $MAX_ITER | stop at: $STOP_AT | model: $MODEL"
echo

for i in $(seq 1 "$MAX_ITER"); do
  [ -f STOP ] && { echo "STOP file present - exiting"; break; }
  [ "$(date +%H:%M)" \> "$STOP_AT" ] && [ "$(date +%H)" -lt 12 ] && { echo "past $STOP_AT - exiting"; break; }

  TS=$(date +%Y%m%dT%H%M%S)
  echo "[$TS] iteration $i/$MAX_ITER starting"

  claude -p \
    --model "$MODEL" \
    --permission-mode acceptEdits \
    --allowedTools 'Read,Write,Edit,Glob,Grep,Bash(make test),Bash(make scan),Bash(python -m pytest tests -q),Bash(python -m ts.cli inspect:*),Bash(git status),Bash(git diff:*)' \
    < "$PROMPT" \
    > "$LOGS/run-$TS.out" 2> "$LOGS/run-$TS.err"

  CODE=$?
  echo "[$(date +%H:%M:%S)] iteration $i finished (exit $CODE)"

  # surface what changed, cheaply
  tail -n 12 PROGRESS.md 2>/dev/null | sed 's/^/    /'
  grep -h 'running_total' COST_LEDGER.md 2>/dev/null | tail -n 1 | sed 's/^/    LEDGER: /'

  # circuit breaker: three consecutive failures means something is structurally broken
  if [ "$CODE" -ne 0 ]; then
    FAILS=$((${FAILS:-0} + 1))
    [ "$FAILS" -ge 3 ] && { echo "3 consecutive failures - stopping"; break; }
  else
    FAILS=0
  fi

  [ "$i" -lt "$MAX_ITER" ] && sleep "$INTERVAL"
done

echo "== loop ended $(date) =="
