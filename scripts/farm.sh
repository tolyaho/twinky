#!/usr/bin/env bash
# Fixture farm. Cycles a channel list, captures whichever are live, sleeps, repeats.
#
#   bash farm.sh                 # run it
#   touch STOP_FARM              # stop after the current round
#
# No Twitch API key: liveness is probed with streamlink, which is already proven to work here.
# CAPTURE ONLY - never enriches. Enrichment costs money and is a deliberate, per-fixture decision.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1          # expects to live in ts/scripts/

CHANNELS=(
  # big EN
  stableronaldo yugi marlon xqc kaicenat jynxzi caseoh_ ironmouse
  # talk-heavy / just-chatting, best odds of a question asked aloud
  hasanabi zackrawrr lacy fanum plaqueboymax
  # RU
  qoqsik sasavot strogo shadowkekw cutierover evelone192 buster
)

MINUTES="${MINUTES:-8}"          # per capture
PER_ROUND="${PER_ROUND:-3}"      # simultaneous captures
SLEEP="${SLEEP:-900}"            # 15 min between rounds
MAX_ROUNDS="${MAX_ROUNDS:-40}"
OUT=evals/fixtures
LOG=.farmlogs
mkdir -p "$LOG"

echo "farm: ${#CHANNELS[@]} channels | ${MINUTES}min x ${PER_ROUND} per round | ${SLEEP}s between"

for round in $(seq 1 "$MAX_ROUNDS"); do
  [ -f STOP_FARM ] && { echo "STOP_FARM present - exiting"; break; }

  # how much disk are we using? bail before filling the machine
  USED=$(du -sm "$OUT" 2>/dev/null | cut -f1)
  if [ "${USED:-0}" -gt 6000 ]; then
    echo "fixtures dir is ${USED}MB - stopping to protect disk"; break
  fi

  echo "[$(date +%H:%M:%S)] round $round - probing"
  LIVE=()
  for C in $(printf '%s\n' "${CHANNELS[@]}" | sort -R); do
    [ "${#LIVE[@]}" -ge "$PER_ROUND" ] && break
    # skip a channel already captured in the last 2 hours
    RECENT=$(find "$OUT" -maxdepth 1 -name "${C}_*" -mmin -120 2>/dev/null | head -1)
    [ -n "$RECENT" ] && continue
    if .venv/bin/streamlink --json "twitch.tv/$C" >/dev/null 2>&1; then
      LIVE+=("$C")
    fi
  done

  if [ "${#LIVE[@]}" -eq 0 ]; then
    echo "  nothing live and uncaptured; sleeping"
  else
    echo "  capturing: ${LIVE[*]}"
    for C in "${LIVE[@]}"; do
      ( .venv/bin/python -m ts.cli capture --channel "$C" --minutes "$MINUTES" --out "$OUT" \
          > "$LOG/${C}-$(date +%s).log" 2>&1 & )
    done
  fi

  sleep "$SLEEP"
done

echo "farm ended $(date). fixtures:"
ls -1 "$OUT" | wc -l
