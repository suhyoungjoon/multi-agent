#!/usr/bin/env bash
# PreToolUse hook for Bash tool calls.
# Reads the pending command from stdin JSON and blocks it (exit 2) if it
# matches a known-dangerous pattern. Exit 0 lets the tool call proceed.
#
# Unlike the Stop hook (check-team-progress.sh), PreToolUse uses an
# exit-code protocol, not JSON: exit 2 blocks the tool call and Claude
# Code shows our stderr to the model as the block reason; exit 0 allows
# it. This exact mechanism was already live-verified in a separate
# learning project (claude-code-understanding, commit d93fb14) before
# being adapted here — the patterns below are that script's, unchanged.

set -euo pipefail

PAYLOAD="$(cat)"

COMMAND="$(printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
cmd = data.get("tool_input", {}).get("command", "")
print(cmd)
')"

if [ -z "$COMMAND" ]; then
    exit 0
fi

LOG_FILE="$HOME/.claude-blocked-commands.log"

block() {
    local reason="$1"
    local pane="${TMUX_PANE:-no-pane}"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    echo "BLOCKED by block-dangerous-bash.sh: $reason" >&2
    echo "Command was: $COMMAND" >&2

    printf '%s | %s | %s | %s\n' "$timestamp" "$pane" "$reason" "$COMMAND" >> "$LOG_FILE" 2>/dev/null || true

    osascript -e "display notification \"pane ${pane}: ${COMMAND}\" with title \"위험 명령 차단\" sound name \"Basso\"" >/dev/null 2>&1 || true

    exit 2
}

# --- Dangerous pattern checks -------------------------------------------

# rm -rf (any target) -- catches rm -rf, rm -fr, rm -r -f, sudo rm -rf, etc.
if printf '%s' "$COMMAND" | grep -Eq '\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\b|\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\b'; then
    block "destructive 'rm -rf'-style recursive force delete is not allowed."
fi

# git push --force / -f (including --force-with-lease variants we still want to flag)
if printf '%s' "$COMMAND" | grep -Eq '\bgit\s+push\b.*(--force\b|--force-with-lease\b|-f\b)'; then
    block "force-pushing to a remote ('git push --force'/'-f') is not allowed."
fi

# git push origin main / git push origin master (main 브랜치 직접 push 차단)
if printf '%s' "$COMMAND" | grep -Eq '\bgit\s+push\s+\S+\s+(main|master)\b'; then
    block "direct push to main/master branch is not allowed. Use a feature branch and PR."
fi

# Reading .env files (cat/less/more/head/tail/vi/nano/cp/mv exposing secrets)
if printf '%s' "$COMMAND" | grep -Eq '(^|[/[:space:]])\.env([.[:space:]]|$)|(^|[/[:space:]])\.env\.[A-Za-z0-9_.-]+'; then
    block "reading or exposing .env files is not allowed (may contain secrets)."
fi

exit 0
