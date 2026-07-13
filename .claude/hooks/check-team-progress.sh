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

MATCHED=$(git status --porcelain 2>/dev/null | cut -c4- | grep -E '^(docs/|memory_store/|cloud-builder/|todo\.py|test_)' || true)

if [ -z "$MATCHED" ]; then
  exit 0
fi

# State tracking: remember the last-reported (HEAD commit + changed paths)
# pair so an untracked/uncommitted file that just sits there doesn't
# re-trigger the same instruction on every single Stop event. HEAD is
# included, not just the path list, so committing the change and then
# editing the same file again is correctly treated as new — the path
# string alone would look identical to the pre-commit state otherwise.
GIT_DIR=$(git rev-parse --git-dir)
STATE_FILE="$GIT_DIR/team-progress-last-state"
HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo "no-commits-yet")
STATE_KEY="${HEAD_SHA}|${MATCHED}"

if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$STATE_KEY" ]; then
  exit 0
fi

printf '%s' "$STATE_KEY" > "$STATE_FILE"

REASON='이번 세션에서 산출물이 바뀌었습니다. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 "## 최근 작업" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라.'
python3 -c "import json, sys; print(json.dumps({'decision': 'block', 'reason': sys.argv[1]}, ensure_ascii=False))" "$REASON"

exit 0
