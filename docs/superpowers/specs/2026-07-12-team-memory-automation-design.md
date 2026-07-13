# 팀 기억 자동화 (Track B) — 설계 문서

> 작성: Claude | 날짜: 2026-07-12
> 상태: 승인됨, 실제 tmux 라이브 검증 완료 (2026-07-12/13 수정 이력)
> - stdout-echo 방식이 Stop 이벤트에서 동작하지 않음을 발견 → JSON `decision:block` 방식으로 교체
> - `wiki-lock.sh`가 macOS에 없는 `flock`에 의존 → `brew install flock`으로 해결(시스템에 설치 완료)
> - 추적 안 된 파일이 남아있으면 매 Stop마다 무한 반복 발화하는 버그 발견 → 변경 경로별 상태 기록으로 재발화 방지
> - (재검토 후) HEAD 커밋 SHA 기반 상태 키는 6-pane 동시 사용 시 한 팀원의 미보고 변경을 다른 팀원의 보고가 조용히 삼켜버릴 수 있음을 발견 → 경로별 콘텐츠 해시(`git hash-object`) 기반 상태 추적으로 재설계

---

## 개요

tmux 6패널 팀원이 세션 응답을 끝낼 때마다, 이번 응답에서 산출물이 바뀌었는지 자동으로 감지해서 바뀌었다면 해당 팀원의 `wiki/team/<이름>.md`에 요약을 남기고 vault에 커밋까지 자동으로 마치는 Claude Code 네이티브 Hook.

- **트리거**: `Stop` 이벤트 (응답 1회 종료마다 — 세션 전체 종료가 아님)
- **게이팅 조건**: `git status --porcelain`으로 역할별 산출물 경로의 변경(추적 파일 수정 + 추적 안 된 신규 파일 모두 포함) 여부 체크. 변경 없으면 아무 것도 안 함
- **상태 추적**: 매칭된 각 경로마다 `경로=콘텐츠해시`를 `.git/team-progress-last-state`에 기록. 이미 보고한 경로+내용 그대로면(추적 안 된 파일이 계속 방치되는 경우 등) 그 경로는 재발화 안 함. 파일 내용이 실제로 바뀌면(커밋 전후 상관없이) 다시 발화. 경로별로 독립 추적하므로, 6개 pane이 서로 다른 파일을 동시에 바꿔도 한쪽의 "이미 보고함" 처리가 다른 쪽의 미보고 변경을 가리지 않음
- **페르소나 판별**: 별도 pane→이름 매핑 없이, Claude가 자기 대화 맥락으로 "나는 어느 팀원인지" 판단 (claude-obsidian의 기존 Stop 훅과 동일 철학)
- **동시성 보호**: vault에 이미 있는 `scripts/wiki-lock.sh`(내부적으로 `flock` 필요 — macOS는 기본 미탑재라 `brew install flock`으로 설치)를 재사용해 같은 파일 동시 쓰기 충돌 방지
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
{"decision": "block", "reason": "이번 세션에서 다음 산출물이 바뀌었습니다: docs/architecture.md. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 \"## 최근 작업\" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라."}
```

`reason`은 이번에 새로 감지된 경로 목록을 앞부분에 명시한다(예: "다음 산출물이 바뀌었습니다: docs/architecture.md, docs/research.md") — 여러 팀원이 겹쳐서 변경했을 때 각 팀원이 자기와 무관한 이미 보고된 경로까지 재기록하는 걸 방지.

**중요 — 설계 변경 배경**: 최초 설계는 claude-obsidian의 Stop 훅 패턴을 그대로 따라 `echo '...' && true`로 plain text를 stdout에 출력하는 방식이었다. 그런데 실제 tmux 라이브 검증(인터랙티브 `claude` 세션에 직접 파일을 수정시키고 관찰)에서, **`Stop` 이벤트는 plain stdout이 모델에게 전달되지 않는 예외 이벤트**임을 확인했다 (공식 문서: "For most events, stdout is written to the debug log but not shown in the transcript. The exceptions are `UserPromptSubmit`, `UserPromptExpansion`, and `SessionStart`" — `Stop`은 이 예외 목록에 없음). 즉 원래 설계로는 훅이 실행되고 텍스트를 출력해도 모델이 그걸 보고 행동하는 일이 전혀 일어나지 않았다 (vault 커밋 0건으로 실측 확인). claude-obsidian 자체의 Stop 훅도 동일 패턴을 쓰고 있어 같은 문제를 안고 있을 가능성이 있다 — 이는 이 프로젝트의 스코프 밖이라 별도로 다루지 않는다.

올바른 방법은 Stop 훅이 `{"decision": "block", "reason": "..."}` JSON을 출력하는 것 — 이러면 Claude Code가 세션 종료를 막고 `reason` 텍스트를 실제로 다음 모델 요청에 전달해 계속 작업하게 만든다. command-type을 쓰는 이유 자체는 그대로 유지: prompt-type Stop 훅은 알려진 "Plugin Hook STDOUT 버그"(`anthropics/claude-code#10875`)로 애초에 신뢰할 수 없어, command-type이 유일한 신뢰 가능한 방식이다.

**감지 대상 경로**(CLAUDE.md의 "역할별 산출물 위치"와 동기화):
`docs/`(민준·지훈·수아·태양), `memory_store/`(서연 예시 프로젝트), `cloud-builder/`(서연 예시 프로젝트), `todo.py`, `test_*`(서연 테스트). 새 프로젝트 디렉토리가 팀 산출물로 추가되면 이 목록도 같이 갱신해야 함.

---

## 데이터 흐름

```
민준 pane에서 응답 완료 (Stop 이벤트)
  → git status --porcelain으로 감지 경로 변경 체크
  → docs/architecture.md가 이번 응답에서 바뀜, 그 경로의 콘텐츠 해시가 상태 파일 기록과 다름(신규)
  → {"decision":"block","reason":"...docs/architecture.md..."} JSON stdout 출력, 상태 파일에 모든 매칭 경로의 최신 해시 갱신
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
- **무한 반복 발화 (실측 발견 후 수정됨)**: 추적 안 된 파일이 커밋되지 않고 계속 방치되면, 상태 추적 없이는 매 Stop마다 동일한 지시가 반복 발화됨(실제 라이브 검증에서 확인). 경로별 콘텐츠 해시를 `.git/team-progress-last-state`에 기록해 해결 — 그 경로 내용이 실제로 더 바뀌기 전까지는 조용
- **동시 pane 간 미보고 변경 유실 (task 리뷰에서 발견 후 수정됨)**: 최초 수정안(HEAD SHA + 전체 변경 경로를 하나의 상태 값으로 취급)은, 한 팀원이 보고를 마친 뒤 다른 팀원의 아직 안 보고된 변경이 있으면 그 팀원의 Stop 이벤트가 조용히 넘어갈 수 있었음. 경로별 독립 추적(위 항목)으로 근본 해결 — 어떤 경로든 아직 보고 안 된 콘텐츠 해시가 있으면 그 경로만 콕 집어 reason에 명시하고 발화
- **`flock` 미설치 (실측 발견 후 해결됨)**: `wiki-lock.sh`가 의존하는 `flock`이 macOS 기본 환경에 없어 락 획득/해제가 실패했음. `brew install flock`으로 설치 완료, 재검증에서 정상 동작 확인

---

## 검증 방법

게이팅 로직(경로 매칭, 상태 추적)은 `test_check_team_progress.py`로 pytest 커버. 실제 Claude Code 통합(JSON 컨텍스트 주입, 페르소나 판단, vault 쓰기)은 셸 스크립트 유닛테스트로 잡을 수 없어 라이브 tmux 세션으로 수동 검증 완료:

1. ✅ `settings.json` 반영 후 실제 인터랙티브 `claude` 세션에서 `docs/architecture.md` 수정 → Stop 훅이 JSON `decision:block` 발화 → 모델이 "민준" 역할 자기판단 → `wiki/team/민준.md`에 실제 append + vault 커밋(`5411022`, 이후 검증용으로 되돌림) 확인
2. ✅ 산출물 변경 없는 응답 뒤에는 훅이 조용함 확인
3. ✅ 같은 상태(추적 안 된 파일 방치)로 재발화하지 않음, 커밋 후 재수정 시에는 다시 발화함, 두 팀원이 겹쳐서 변경해도 서로의 미보고 변경을 가리지 않음, 무관한 커밋이 다른 미보고 경로를 잘못 재발화시키지 않음을 `test_check_team_progress.py`의 상태 추적 테스트 6건(단일 pane 3건 + 동시성 2건 + reason 특정 경로 명시 1건)으로 확인
4. `wiki-lock.sh` 동시 pane 시뮬레이션(같은 파일 동시 쓰기)은 기존대로 미실시(vault 자체 테스트로 커버 — 검증 방법 섹션의 원래 근거 유지). 서로 다른 파일 동시 변경 시나리오는 위 3번에서 커버됨

---

## 제외 범위

- **SessionStart 훅(세션 시작 시 이전 맥락 자동 로드)** — 이번 설계는 "저장" 방향만 다룸. 로드 방향은 자연스러운 후속 과제지만 별도 스펙으로 분리
- **페르소나 판별의 결정적(deterministic) 매핑** (`$TMUX_PANE` 기반 등) — LLM 자기판단 방식을 채택했으므로 범위 밖. 오판단 빈도가 실제로 문제가 되면 재검토
- **claude-obsidian 자체 플러그인 훅 수정** — 이 설계는 `multi-agent` 프로젝트 로컬 `.claude/settings.json`에만 적용되는 별도 훅이며, claude-obsidian 플러그인 자체(user-scope)는 건드리지 않음
