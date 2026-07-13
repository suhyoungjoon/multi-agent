# 위험 명령 차단 (Track C) — 설계 문서

> 작성: Claude | 날짜: 2026-07-13
> 상태: 승인됨

---

## 개요

tmux 6패널 팀원이 Bash 도구를 호출할 때마다, 명령이 알려진 위험 패턴(재귀 강제 삭제, force push, main 직접 push, `.env` 노출)에 해당하면 실행 자체를 막는 Claude Code 네이티브 `PreToolUse` Hook.

- **트리거**: `PreToolUse` 이벤트, `matcher: "Bash"` — Bash 도구가 실제로 실행되기 **직전**
- **차단 방식**: exit code 2 (Stop 훅의 JSON `decision` 프로토콜과 다름 — PreToolUse는 exit code로 통제: 2=차단+stderr가 Claude에게 이유로 전달, 0=허용)
- **배경**: `setup-team-v2.sh`가 모든 pane을 `--dangerously-skip-permissions`로 띄우기 때문에, 현재 team1에는 위험 명령을 막을 장치가 전혀 없음 — 대화형 승인 프롬프트 자체가 뜨지 않아 watchdog.sh의 자동 승인 로직도 관여하지 않음. 이 훅이 사실상 유일한 안전망이 됨
- **기존 자산**: `~/workspaces/claude-code-understanding`(Track C 학습 프로젝트)의 `block-dangerous-bash.sh`를 검증된 선례로 그대로 재사용

---

## Hook 정의

`multi-agent/.claude/settings.json`에 기존 `Stop` 훅과 함께 `PreToolUse` 추가:

```json
{
  "hooks": {
    "Stop": [ /* 기존 그대로 (Track B) */ ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/block-dangerous-bash.sh" }
        ]
      }
    ]
  }
}
```

`.claude/hooks/block-dangerous-bash.sh`는 stdin으로 PreToolUse payload(JSON)를 받아 `tool_input.command`를 추출한 뒤 아래 4가지 패턴을 검사한다. 매칭되면 stderr에 차단 사유+원본 명령을 출력하고 `exit 2`(Claude Code가 도구 호출을 막고 stderr 내용을 Claude에게 전달 — Claude는 이걸 보고 다른 방법을 시도하거나 사용자에게 확인을 구함). 매칭 없으면 `exit 0`.

**차단 패턴** (`claude-code-understanding`의 선례 그대로):

| 패턴 | 예시 |
|---|---|
| `rm -rf` 계열 | `rm -rf`, `rm -fr`, `rm -r -f`, `sudo rm -rf` (옵션 순서/결합 무관하게 재귀+강제 조합 탐지) |
| `git push --force`/`-f` | `--force-with-lease` 포함 |
| `git push origin main/master` | 직접 push — 이 저장소의 실제 워크플로우(feature 브랜치 + PR)와 정확히 일치 |
| `.env` 파일 읽기/노출 | `cat`/`less`/`head`/`tail`/`cp`/`mv` 등으로 `.env*` 접근 |

---

## 알림 + 로그

`block()` 함수에 두 가지를 추가한다 (watchdog.sh의 `notify()`/`LOG_FILE` 관례와 동일 패턴):

1. **macOS 데스크톱 알림**: `osascript -e 'display notification "..." with title "위험 명령 차단" sound name "Basso"'` — `$TMUX_PANE`(예: `%3`)과 차단된 명령 요약을 표시. 페르소나 이름까지는 해석하지 않음(Studio의 `team_config.py`와 결합하지 않기 위해 — Track C 훅은 Track D Python 코드에 의존하지 않는 독립 자산으로 유지)
2. **로그 파일**: `~/.claude-blocked-commands.log`에 `타임스탬프 | pane | 사유 | 원본 명령`을 append

---

## 에러 처리

- stdin payload가 비어있거나 JSON 파싱 실패 → 조용히 `exit 0` (차단하지 않음 — 훅 자체 오류로 팀 작업이 멈추면 안 됨)
- `osascript` 실패(알림 권한 없음 등) → 무시하고 계속 진행(차단 자체는 알림 성공 여부와 무관하게 적용됨 — 알림은 부가 기능)
- 매칭 안 되는 모든 다른 Bash 명령 → 영향 없음, 기존 동작 그대로(exit 0)

---

## 검증 방법

`test_block_dangerous_bash.py`(repo root, `test_check_team_progress.py`와 같은 위치)에서 pytest로 검증:

1. 4가지 위험 패턴 각각에 대해 stdin에 PreToolUse JSON payload를 넣어 스크립트 실행 → `exit code == 2`, stderr에 차단 사유 포함 확인
2. 안전한 일반 명령(`ls`, `git status`, `git push origin feature/foo` 등) → `exit code == 0`, stderr 비어있음 확인
3. stdin이 비어있거나 잘못된 JSON일 때 → `exit code == 0`(조용히 통과)
4. `osascript` 호출은 macOS 전용 부가 기능이라 실제 알림을 띄우는지는 테스트하지 않음 — 차단 여부(exit code)만 검증. `osascript` 실패 시에도 차단 자체는 정상 동작하는지 별도 확인(예: `PATH`에서 `osascript` 제거한 환경으로 실행)

---

## 제외 범위

- **watchdog.sh 정리** — watchdog.sh의 "권한 승인 대기 감지 → 자동 승인" 로직은 `--dangerously-skip-permissions` 환경에서 사실상 죽은 코드지만, 이번 스코프는 아님(Studio 때와 동일 원칙: 기존 스크립트는 건드리지 않고 그대로 폴백으로 유지)
- **차단 패턴 확장/커스터마이징 UI** — 4가지 패턴은 하드코딩. 패턴 추가/제거가 자주 필요해지면 별도 설정 파일로 분리하는 걸 재검토
- **페르소나 이름 해석** — 알림/로그는 `$TMUX_PANE` 원시 값만 표시, "이건 민준이 시도한 명령"처럼 이름으로 해석하지 않음
