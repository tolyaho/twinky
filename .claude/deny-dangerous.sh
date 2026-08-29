#!/usr/bin/env bash
# PreToolUse hook. Claude Code passes the tool call as JSON on stdin and reads a JSON
# decision on stdout. Blocks destructive or irreversible commands during unattended runs.
INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)

BLOCK='git push|git reset --hard|git clean|rm -rf|rm -r |sudo |dd if=|mkfs|:>|curl .*\| *(ba)?sh|npm publish|pip install'
PROTECT='evals/fixtures|cache/llm|\.env|\.capture_salt'

if printf '%s' "$CMD" | grep -qE "$BLOCK"; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"blocked by overnight guardrail: %s"}}' "$CMD"
  exit 0
fi
if printf '%s' "$CMD" | grep -qE 'rm|mv|truncate' && printf '%s' "$CMD" | grep -qE "$PROTECT"; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"refusing to touch fixtures, cache or secrets"}}'
  exit 0
fi
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
