#!/bin/bash
# Stop hook: detect whether team-output paths changed this response.
# If so, print an instruction telling Claude to record it in the vault.
# Must never fail the hook chain — always exits 0, silent when there's
# nothing to report.
set -uo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

if git diff --name-only HEAD 2>/dev/null | grep -qE '^(docs/|memory_store/|cloud-builder/|todo\.py|test_)'; then
  echo 'TEAM_PROGRESS_CHANGED: 이번 세션에서 산출물이 바뀌었습니다. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 "## 최근 작업" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라.'
fi

exit 0
