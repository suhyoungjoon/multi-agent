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

if git status --porcelain 2>/dev/null | cut -c4- | grep -qE '^(docs/|memory_store/|cloud-builder/|todo\.py|test_)'; then
  REASON='이번 세션에서 산출물이 바뀌었습니다. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 "## 최근 작업" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라.'
  python3 -c "import json, sys; print(json.dumps({'decision': 'block', 'reason': sys.argv[1]}, ensure_ascii=False))" "$REASON"
fi

exit 0
