# 팀 기억 자동화 (Track B) — 설계 문서

> 작성: Claude | 날짜: 2026-07-12
> 상태: 승인됨 (2026-07-12 수정: 실제 tmux 라이브 검증에서 원래 설계한 stdout-echo 방식이 동작하지 않는 것을 발견 — Hook 정의를 JSON `decision:block` 방식으로 교체)

---

## 개요

tmux 6패널 팀원이 세션 응답을 끝낼 때마다, 이번 응답에서 산출물이 바뀌었는지 자동으로 감지해서 바뀌었다면 해당 팀원의 `wiki/team/<이름>.md`에 요약을 남기고 vault에 커밋까지 자동으로 마치는 Claude Code 네이티브 Hook.

- **트리거**: `Stop` 이벤트 (응답 1회 종료마다 — 세션 전체 종료가 아님)
- **게이팅 조건**: `git diff --name-only HEAD`로 역할별 산출물 경로 변경 여부 체크. 변경 없으면 아무 것도 안 함
- **페르소나 판별**: 별도 pane→이름 매핑 없이, Claude가 자기 대화 맥락으로 "나는 어느 팀원인지" 판단 (claude-obsidian의 기존 Stop 훅과 동일 철학)
- **동시성 보호**: vault에 이미 있는 `scripts/wiki-lock.sh`를 재사용해 같은 파일 동시 쓰기 충돌 방지
- **기존 자산과의 관계**: `claude-obsidian`의 `hooks.json` 패턴(command-type, STDOUT 기반 조건부 안내문 주입)을 그대로 재사용. 이 프로젝트(`multi-agent`)에는 로컬 `wiki/` 폴더가 없어 claude-obsidian 자체 플러그인 훅은 여기서 발화하지 않으므로, 별도로 이 훅을 정의해야 함

---

## Hook 정의

`multi-agent/.claude/settings.json` (신규 파일 — 기존 `settings.local.json`은 로컬 전용 권한만 담당하므로 분리):

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/check-team-progress.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/check-team-progress.sh`가 게이팅 조건을 만족하면 다음 형태의 **JSON**을 stdout으로 출력한다:

```json
{"decision": "block", "reason": "이번 세션에서 산출물이 바뀌었습니다. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 \"## 최근 작업\" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라."}
```

**중요 — 설계 변경 배경**: 최초 설계는 claude-obsidian의 Stop 훅 패턴을 그대로 따라 `echo '...' && true`로 plain text를 stdout에 출력하는 방식이었다. 그런데 실제 tmux 라이브 검증(인터랙티브 `claude` 세션에 직접 파일을 수정시키고 관찰)에서, **`Stop` 이벤트는 plain stdout이 모델에게 전달되지 않는 예외 이벤트**임을 확인했다 (공식 문서: "For most events, stdout is written to the debug log but not shown in the transcript. The exceptions are `UserPromptSubmit`, `UserPromptExpansion`, and `SessionStart`" — `Stop`은 이 예외 목록에 없음). 즉 원래 설계로는 훅이 실행되고 텍스트를 출력해도 모델이 그걸 보고 행동하는 일이 전혀 일어나지 않았다 (vault 커밋 0건으로 실측 확인). claude-obsidian 자체의 Stop 훅도 동일 패턴을 쓰고 있어 같은 문제를 안고 있을 가능성이 있다 — 이는 이 프로젝트의 스코프 밖이라 별도로 다루지 않는다.

올바른 방법은 Stop 훅이 `{"decision": "block", "reason": "..."}` JSON을 출력하는 것 — 이러면 Claude Code가 세션 종료를 막고 `reason` 텍스트를 실제로 다음 모델 요청에 전달해 계속 작업하게 만든다. command-type을 쓰는 이유 자체는 그대로 유지: prompt-type Stop 훅은 알려진 "Plugin Hook STDOUT 버그"(`anthropics/claude-code#10875`)로 애초에 신뢰할 수 없어, command-type이 유일한 신뢰 가능한 방식이다.

**감지 대상 경로**(CLAUDE.md의 "역할별 산출물 위치"와 동기화):
`docs/`(민준·지훈·수아·태양), `memory_store/`(서연 예시 프로젝트), `cloud-builder/`(서연 예시 프로젝트), `todo.py`, `test_*`(서연 테스트). 새 프로젝트 디렉토리가 팀 산출물로 추가되면 이 목록도 같이 갱신해야 함.

---

## 데이터 흐름

```
민준 pane에서 응답 완료 (Stop 이벤트)
  → git diff --name-only HEAD 체크
  → docs/architecture.md가 이번 응답에서 바뀜 → {"decision":"block","reason":"..."} JSON stdout 출력
  → Claude Code가 세션 종료를 막고 reason 텍스트를 다음 모델 요청에 컨텍스트로 주입
  → 민준 페르소나가 "나는 민준이다" 판단
  → cd ~/workspaces/multi-agent-wiki && bash scripts/wiki-lock.sh acquire wiki/team/민준.md
  → wiki/team/민준.md "## 최근 작업" 섹션에 3~5문장 append (append, 전체 덮어쓰기 아님 — hot.md와 달리 팀원별 누적 이력이므로)
  → git add wiki/team/민준.md && git commit
  → bash scripts/wiki-lock.sh release wiki/team/민준.md
```

---

## 에러 처리 / 동시성

- **동시 커밋 충돌**: 두 pane이 비슷한 시점에 서로 다른 파일(`쭌.md`, `민준.md`)을 각각 커밋하면 git 자체는 문제없음(다른 파일이라 충돌 없음). 같은 파일에 동시에 쓰는 경우만 `wiki-lock.sh`가 막아줌 — 락을 못 잡으면 해당 pane은 이번 갱신을 건너뜀(다음 Stop 때 재시도되므로 데이터 유실 아님)
- **페르소나 오판단**: LLM이 "나는 누구인지" 잘못 판단할 가능성은 ADR-003에서 이미 확인된 기존 한계(위임 체계가 자동으로 완벽하게 지켜지지 않음). 이 설계로 100% 방지 불가능하며, 잘못 기록된 항목은 사람이 나중에 wiki에서 직접 수정. 치명적이지 않은 실패 모드로 간주
- **vault 디렉토리 접근 실패**: `cd ~/workspaces/multi-agent-wiki` 실패 시, 훅이 아니라 지시받은 Claude가 실행하는 Bash 단계에서 조용히 실패 → 스킵됨(치명적 아님)
- **git diff 대상 경로 누락**: 감지 경로 목록에 없는 새 디렉토리의 변경은 감지되지 않음 — 목록 갱신을 문서화된 유지보수 항목으로 남김

---

## 검증 방법

셸 훅 설정이라 pytest 대상이 아님. 수동 시나리오 검증:
1. `settings.json` 반영 후 한 pane에서 `docs/architecture.md`를 실제로 수정하는 응답 실행
2. 응답 종료 후 `wiki/team/<해당 이름>.md`에 새 항목이 append됐는지, vault에 새 커밋이 생겼는지 확인
3. 산출물 변경이 없는 응답 뒤에는 아무 일도 안 일어나는지 확인(과도한 커밋 방지 확인)
4. 두 pane에서 거의 동시에 서로 다른 팀원 파일을 갱신하는 상황을 시뮬레이션해 `wiki-lock.sh` 개입 여부 확인

---

## 제외 범위

- **SessionStart 훅(세션 시작 시 이전 맥락 자동 로드)** — 이번 설계는 "저장" 방향만 다룸. 로드 방향은 자연스러운 후속 과제지만 별도 스펙으로 분리
- **페르소나 판별의 결정적(deterministic) 매핑** (`$TMUX_PANE` 기반 등) — LLM 자기판단 방식을 채택했으므로 범위 밖. 오판단 빈도가 실제로 문제가 되면 재검토
- **claude-obsidian 자체 플러그인 훅 수정** — 이 설계는 `multi-agent` 프로젝트 로컬 `.claude/settings.json`에만 적용되는 별도 훅이며, claude-obsidian 플러그인 자체(user-scope)는 건드리지 않음
