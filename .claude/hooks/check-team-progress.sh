#!/bin/bash
# Stop hook: detect whether team-output paths changed this response.
# If so, emit {"decision":"block","reason":"..."} JSON so Claude Code
# prevents the stop and feeds `reason` to the model as the next
# instruction. Plain stdout text does NOT reach the model for the Stop
# event (Stop is not in the stdout-passthrough exception list — only
# UserPromptSubmit/UserPromptExpansion/SessionStart get that), so the
# JSON decision protocol is required, not optional.
# Must never fail the hook chain — always exits 0, silent when there's
# nothing to report.
set -uo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

MATCHED_PATHS=$(git status --porcelain 2>/dev/null | cut -c4- | grep -E '^(docs/|memory_store/|cloud-builder/|todo\.py|test_)' || true)

if [ -z "$MATCHED_PATHS" ]; then
  exit 0
fi

# State tracking: remember, per matched path, the content hash we last
# reported for it. Content hash (not HEAD commit) is used per path so that
# an unrelated commit elsewhere in the repo never invalidates a
# still-pending path's already-reported status, while genuinely re-editing
# a path (even across a commit boundary) always produces a new hash and
# re-fires.
#
# The state file itself is scoped per tmux pane ($TMUX_PANE), not shared
# across all 6 panes. A single shared ledger was tried and found broken:
# all 6 panes poll the SAME git working tree, so if 민준 edits
# docs/architecture.md and Stops while 지훈's docs/research.md edit is
# already sitting on disk (still mid-turn, not yet Stopped), 민준's hook
# run sees both files as "currently matched" and would mark research.md
# as reported before 지훈's own Stop ever ran — silently swallowing
# 지훈's contribution. Since each tmux pane gets its own $TMUX_PANE value,
# giving each pane an independent ledger means one pane's bookkeeping can
# never suppress another pane's report. Outside tmux there's only one
# consumer, so the $TMUX_PANE-less fallback name is safe to share.
GIT_DIR=$(git rev-parse --git-dir)
STATE_FILE="$GIT_DIR/team-progress-last-state${TMUX_PANE:+-$TMUX_PANE}"
touch "$STATE_FILE"

NEW_PATHS=""
while IFS= read -r path; do
  [ -z "$path" ] && continue
  content_hash=$(git hash-object "$path" 2>/dev/null) || continue
  token="${path}=${content_hash}"
  if ! grep -qxF "$token" "$STATE_FILE"; then
    NEW_PATHS="${NEW_PATHS}${path}"$'\n'
  fi
done <<< "$MATCHED_PATHS"

if [ -z "$NEW_PATHS" ]; then
  exit 0
fi

# Rewrite the state file with the current content hash for every currently
# matched path (not just the newly-detected ones), so paths another pane
# already reported stay marked as reported.
STATE_TMP="$STATE_FILE.tmp.$$"
: > "$STATE_TMP"
while IFS= read -r path; do
  [ -z "$path" ] && continue
  content_hash=$(git hash-object "$path" 2>/dev/null) || continue
  echo "${path}=${content_hash}" >> "$STATE_TMP"
done <<< "$MATCHED_PATHS"
mv "$STATE_TMP" "$STATE_FILE"

# Join with ", " by hand rather than `paste -sd`: BSD paste (macOS default)
# treats a multi-character -d argument as a *rotating* delimiter list, not
# a literal separator, producing inconsistent joins like "a,b c" instead
# of "a, b, c".
CHANGED_LIST=$(printf '%s' "$NEW_PATHS" | awk 'NF { printf "%s%s", sep, $0; sep=", " }')

REASON="이번 세션에서 다음 산출물이 바뀌었습니다: ${CHANGED_LIST}. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 \"## 최근 작업\" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라."
python3 -c "import json, sys; print(json.dumps({'decision': 'block', 'reason': sys.argv[1]}, ensure_ascii=False))" "$REASON"

exit 0
