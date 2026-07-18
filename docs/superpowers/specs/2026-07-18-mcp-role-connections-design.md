# MCP 역할별 연결 (Track C 후반) — 설계 문서

> 작성: Claude | 날짜: 2026-07-18
> 상태: 승인됨

---

## 개요

현재 team1의 6개 패널은 모두 동일한 도구 세트로 기동된다(`setup-team-v2.sh`가 `claude --model X --dangerously-skip-permissions`만 호출). 페르소나별로 실제 필요한 외부 연결(라이브러리 문서 조회, 브라우저 조작, GitHub API)이 다른데도 구분이 없다. Claude Code CLI의 `--mcp-config <file>`(지정 파일의 MCP 서버만 로드) + `--strict-mcp-config`(그 외 전역/프로젝트 MCP 설정 완전 무시) 플래그를 이용해, 페르소나별로 서로 다른 MCP 서버 세트를 부여한다.

- **범위**: 기존 6명 개발팀 페르소나에 한정. "일상생활 관리" 등 도메인 확장은 이번 스코프 밖(사용자와 논의했으나 별도 트랙으로 분리하기로 함)
- **보안 발견**: 프로젝트 레벨 MCP 설정(`~/.claude.json`)에 GitHub MCP가 평문 토큰(`Authorization: Bearer ghp_...`)으로 등록되어 있음이 확인됨. 이번 설계에서 새로 만드는 `.mcp/*.json` 파일에는 토큰을 절대 평문으로 넣지 않고 환경변수 참조(`${GITHUB_PAT}`)만 사용한다. 기존 `~/.claude.json`의 평문 토큰 자체를 정리/회전하는 것은 사용자 판단 영역으로 스코프 밖에 둔다.
- **메커니즘 검증**: 브레인스토밍 중 실제로 `claude --mcp-config <파일> --strict-mcp-config -p "..."`를 라이브로 실행해, 지정한 MCP(context7)의 도구만 노출되고 다른 건 전혀 안 보이는 것을 확인함. 단, 이 저장소 안에서 실행하면 Track B의 `Stop` 훅(`check-team-progress.sh`)이 함께 발동하는 부작용이 있음이 발견됨 — 검증 방법 섹션에서 이를 회피하는 절차를 명시한다.

---

## 아키텍처

```
team.yaml (각 멤버에 mcp_config 필드 추가)
    │
    ├─ 쭌       mcp_config: null
    ├─ 민준     mcp_config: .mcp/민준.json      (context7)
    ├─ 지훈     mcp_config: null                 (네이티브 WebSearch/WebFetch로 충분)
    ├─ 수아     mcp_config: .mcp/수아.json      (browser)
    ├─ 서연     mcp_config: .mcp/서연.json      (github)
    └─ 태양     mcp_config: .mcp/태양.json      (browser + github)

setup-team-v2.sh: 패널 launch 시 team.yaml의 mcp_config가 있으면
  claude --model X --mcp-config .mcp/<이름>.json --strict-mcp-config --dangerously-skip-permissions
없으면 --mcp-config/--strict-mcp-config 없이 기존과 동일하게 launch
```

쭌/지훈에게 지금 MCP를 안 주는 이유:
- 쭌은 "직접 작업 금지, 위임만" 원칙과 일치 — 코딩/조사 도구가 애초에 불필요
- 지훈은 Claude Code CLI 내장 `WebSearch`/`WebFetch`(MCP 아님, 항상 사용 가능)로 웹 리서치가 이미 커버됨 — 특화 리서치 MCP(Exa/Firecrawl 등)는 API 키 발급 등 복잡도 대비 지금 시점 실익이 낮다고 판단, 필요해지면 후속 작업으로 추가

---

## `team.yaml` 스키마 확장

각 멤버 항목에 `mcp_config` 필드 추가(값 없으면 `null`):

```yaml
  - name: 민준
    pane: 1
    model: claude-sonnet-4-6
    role: |
      ...(기존과 동일, 변경 없음)...
    reports_to: 쭌
    outputs: [docs/architecture.md, docs/api-spec.md, docs/data-model.md]
    hub_for: [지훈, 서연, 태양]
    owns_files: []
    mcp_config: .mcp/민준.json
```

6명 전원이 이 필드를 갖되 쭌/지훈은 `mcp_config: null`.

---

## `.mcp/*.json` 파일

저장소 루트에 `.mcp/` 디렉토리 신설. Claude Code 표준 `--mcp-config` JSON 형식.

**`.mcp/민준.json`** (context7 — 라이브러리 문서 조회, 인증 불필요):
```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

**`.mcp/수아.json`** (browser — Playwright 기반, 인증 불필요):
```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

**`.mcp/서연.json`** (github — 원격 HTTP, 토큰은 환경변수 참조):
```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    }
  }
}
```

**`.mcp/태양.json`** (browser + github 결합):
```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    }
  }
}
```

---

## 토큰 처리

저장소 루트 `.env`(이미 `.gitignore`에 `.env` 등록되어 있어 안전)에 `GITHUB_PAT=ghp_...` 형태로 실값을 둔다. `setup-team-v2.sh`가 패널을 띄우기 전 `.env`가 있으면 `set -a && source .env && set +a`로 로드한다. `.env`가 없으면 `${GITHUB_PAT}`이 빈 문자열로 치환되어 GitHub MCP 연결만 실패하고, 해당 도구 없이 그 패널은 계속 정상 동작한다(다른 패널/전체 팀 기동을 막지 않음).

---

## `setup-team-v2.sh` 연동

패널 launch 루프에서 `team.yaml`의 `mcp_config` 값을 배열로 읽어온다(기존 `MEMBER_NAMES`/`MEMBER_MODELS`와 동일한 `while read` + 인라인 `python3 -c` 패턴, bash 3.2 호환 — Track A에서 이미 검증된 패턴 재사용). 값이 있는 인덱스는:

```bash
claude --model "${MEMBER_MODELS[$i]}" \
  --mcp-config "${MEMBER_MCP_CONFIGS[$i]}" --strict-mcp-config \
  --dangerously-skip-permissions
```

값이 없으면(`mcp_config: null` → 빈 문자열) 기존과 동일하게 `--mcp-config`/`--strict-mcp-config` 없이 launch. `team.yaml`이 없거나 `mcp_config` 필드 자체가 없어도 마찬가지로 이 플래그들을 생략하므로, 이 기능이 통째로 실패해도 팀 기동 자체는 막히지 않는다(Track A에서 확립한 폴백 원칙 유지).

---

## 검증 방법

- `.mcp/*.json` 각각 JSON 유효성 확인 (`python3 -c "import json; json.load(open(...))"`)
- `.mcp/서연.json`, `.mcp/태양.json`에 실제 토큰 패턴(`ghp_[A-Za-z0-9]+` 등)이 없고 `${GITHUB_PAT}` 참조만 있는지 정규식으로 확인 — 평문 토큰 실수 커밋 방지
- `team.yaml`의 `mcp_config` 필드가 `team_config.py`에서 다른 필드와 동일하게 올바르게 파싱되는지 pytest로 확인
- `setup-team-v2.sh`: `bash -n` 문법 검사 + `MEMBER_MCP_CONFIGS`/플래그 조립 로직만 떼어내 독립 실행하는 드라이런(Track A의 `MEMBER_NAMES` 검증과 동일 패턴)
- **라이브 스모크테스트**: 반드시 이 저장소 밖의 임시 디렉토리(예: `/tmp` 하위, `.claude/settings.json`이 없는 곳)에서 `claude --mcp-config <파일 절대경로> --strict-mcp-config -p "..."`로 실제 세션을 1회 띄워 의도한 MCP 도구만 노출되는지 확인한다. **이 저장소 안에서 실행하면 Track B의 Stop 훅이 함께 발동하므로 반드시 피할 것.**
- 실제 6패널 전체 기동(`setup-team-v2.sh` 실행)까지는 스코프 아님 — Track A와 동일 원칙(배열/플래그 조립이 올바른지는 코드 리뷰 + 드라이런으로 충분하다고 판단)

---

## 제외 범위

- 지훈/쭌에게 지금 MCP 부여하는 것 (네이티브 도구로 충분, 필요시 후속 작업)
- `~/.claude.json`의 기존 전역 GitHub MCP 항목(평문 토큰) 자체를 정리/회전하는 것 — 사용자 판단 영역
- MCP 서버 연결 실패 시 자동 재시도/폴백 로직 — 실패해도 해당 패널의 그 도구만 못 쓰게 될 뿐, Claude Code 기본 동작에 맡김
- `context7`/`playwright-mcp` 최초 실행 시 `npx` 패키지 다운로드 지연 최적화(사전 설치 등)
- "일상생활 관리" 등 개발팀 외 도메인으로의 확장 (브레인스토밍 중 논의했으나 이번 스코프 밖으로 명시적으로 분리)
