# Team Structure

This project runs a tmux multi-agent team in session `team1`, window `0`, panes 0-5.
Each pane runs its own Claude Code instance acting as a team member persona.

**팀 구성, 역할, 보고체계, 산출물 경로는 `team.yaml`을 단일 소스로 참고하라.** 이 파일이 이전에 있던 표/다이어그램을 대체한다.

## MEMBER_SYSTEM_RULES

**tmux 메시지 전송 규칙 (모든 페르소나 공통):**
메시지 텍스트와 Enter는 절대 한 번의 `send-keys` 호출로 합치지 않는다. 반드시 3단계로 분리:
1. `tmux send-keys -t team1:0.N '메시지내용'`
2. `sleep 1.5`
3. `tmux send-keys -t team1:0.N Enter`

전송 후에는 `tmux capture-pane -t team1:0.N -p | tail -8`로 실제 제출됐는지(입력줄에 남아있지 않은지) 확인하기 전까지 "보냈다/전달했다"고 말하지 않는다.

**역할별 산출물 위치 (모든 페르소나는 실질적 작업 결과를 파일로 남긴다):**
- 민준 → `docs/architecture.md`, `docs/api-spec.md`, `docs/data-model.md`
- 지훈 → `docs/research/<topic>.md` (주제별 파일)
- 수아 → `docs/design/user-flow.md`, `docs/design/component-spec.md`
- 서연 → 코드 자체 + README/주석 (별도 문서 불필요)
- 태양 → `docs/review/<대상파일명>-review.md`

## Wiki Vault

팀의 영구 지식베이스는 코드 저장소와 분리된 Obsidian vault에 있다:

```
~/workspaces/multi-agent-wiki/
```

- claude-obsidian 플러그인(`claude-obsidian@agricidaniel-claude-obsidian`, user scope)으로 설치됨
- `/wiki` (정확히는 `/claude-obsidian:wiki-cli`) 명령으로 스캐폴딩됨
- `wiki/team/` — 팀원별 프로필 (쭌.md, 민준.md, 지훈.md, 수아.md, 서연.md, 태양.md) + `_index.md`(보고 체계 다이어그램)
- `wiki/architecture/`, `wiki/research/`, `wiki/reviews/`, `wiki/decisions/`(ADR) — 각 역할 산출물의 장기 보관/검색용 인덱스

`docs/`(코드 저장소 내부)는 진행 중 작업의 1차 산출물이고, `wiki/`(별도 vault)는 그것들을 누적·검색 가능하게 정리하는 2차 지식베이스다.
