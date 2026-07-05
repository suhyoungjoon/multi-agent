# Advanced Agent Studio (Track D) v1 — 설계 문서

> 작성: Claude | 날짜: 2026-07-05
> 상태: 승인됨

---

## 개요

tmux 6패널 멀티에이전트 팀(Track A)의 상태를 보고, 멈춘 패널에 개입하고, 팀의 영구 지식베이스(wiki, Track B)를 조회/저장할 수 있는 로컬 웹 대시보드.

- **인터페이스**: 브라우저 웹 UI (로컬 웹앱)
- **접근 범위 (v1)**: 맥북 로컬 + 같은 LAN 내 다른 기기(예: 윈도우 PC). 외부 인터넷 접근은 v1 범위 밖(추후 과제)
- **핵심 문제 3가지**: (1) 팀 상태 가시성 대시보드 (2) 멈춘 패널 재시작/역할 재주입/compact 트리거 (3) wiki 메모리 읽기+쓰기
- **범위 밖 (v1)**: 패널에 텍스트 메시지 전송, 권한 승인/거부 대응 — 둘 다 기존 Claude 앱으로 처리하므로 Studio가 중복 구현하지 않음
- **기존 스크립트와의 관계**: `setup-team-v2.sh`, `watchdog.sh`는 삭제하지 않고 그대로 유지. Studio에 문제가 생기면 언제든 기존 방식으로 폴백 가능

---

## 디렉터리 구조

```
multi-agent/
└── studio/
    ├── main.py            # FastAPI 앱 진입점 + 인증 미들웨어
    ├── tmux_control.py     # capture-pane/send-keys 래퍼 (watchdog.sh 원시 동작 이식)
    ├── watchdog_loop.py    # 배경 asyncio 태스크: stuck 감지, context 폴링, compact 트리거
    ├── team_config.py      # 팀 구성 로더 (team.yaml 없으면 setup-team-v2.sh 배열로 폴백)
    ├── wiki_bridge.py       # multi-agent-wiki 볼트 read/write, 템플릿 기반 저장
    ├── auth.py             # LAN 접근용 토큰 인증 미들웨어
    ├── static/, templates/ # 서버렌더링 + 폴링(2~3초) 기반 프론트, 바닐라 JS
    └── tests/
        ├── test_tmux_control.py
        ├── test_watchdog_loop.py
        └── test_api.py
```

단일 FastAPI 프로세스가 백엔드+프론트를 함께 서빙.

---

## 컴포넌트

| 모듈 | 역할 |
|------|------|
| `tmux_control.py` | `capture_pane(idx)`, `send_keys(idx, text)`, `send_enter(idx)` — watchdog.sh의 "텍스트 전송 → sleep 1.5 → Enter" 3단계 규칙을 함수로 이식 |
| `watchdog_loop.py` | 기존 watchdog.sh 감지 로직(정체 감지 `STUCK_THRESHOLD`, 컨텍스트 임계치 `CONTEXT_THRESHOLD`/`COMPACT_THRESHOLD`, `/clear` 추정 감지)을 asyncio 태스크로 재구현. 임계치 초과 시 기존과 동일하게 자동 조치를 실행하고, 결과를 in-memory 상태로 노출 |
| `team_config.py` | v1은 team.yaml 스키마가 아직 없으므로, `setup-team-v2.sh`의 `MEMBER_NAMES`/`MEMBER_MODELS` 배열을 파싱하는 폴백 파서로 시작. team.yaml이 나오면 이 모듈만 교체 |
| `wiki_bridge.py` | wiki 검색(`GET /api/wiki/search`), hot cache 조회(`GET /api/wiki/hot`), **템플릿 기반 저장**(`POST /api/wiki/save`) — 사용자가 입력한 텍스트를 정해진 frontmatter 템플릿에 넣어 파일로 씀. LLM 합성(`claude -p` 헤드리스 호출)은 v1 범위 밖 |
| `auth.py` | LAN 노출에 대비한 최소 인증. 토큰은 `.env`에 저장(기존 프로젝트 관례와 일치), 요청 헤더로 토큰 비교 |

---

## 데이터 흐름

```
watchdog_loop (2초 주기, 백그라운드)
  → 각 패널 tmux capture-pane
  → 상태 dict 갱신 (stuck 여부 / idle 여부 / context %)
  → 임계치 초과 시: 기존과 동일하게 자동 조치 실행 + 상태에 기록

프론트 (2~3초 폴링)
  GET  /api/status              → 패널 카드 렌더 (이름 / 최근 줄 / stuck 여부 / context %)
  GET  /api/wiki/hot             → 메모리 패널: hot cache 표시
  GET  /api/wiki/search?q=      → 메모리 패널: 키워드 검색 결과
  POST /api/wiki/save            → 메모리 패널: 템플릿 저장
  POST /api/pane/{idx}/restart   → tmux_control.reinject_role() 직접 호출
  POST /api/pane/{idx}/compact   → tmux_control로 /compact 전송 + 완료 대기 + /context 재확인
```

---

## 에러 처리 / 폴백

- tmux 세션(`team1`)이 없으면 `/api/status`가 503 + "세션 없음, setup-team-v2.sh를 먼저 실행하세요" 안내 반환
- team.yaml(또는 폴백 배열) 파싱 실패 시 조용히 무너지지 않고 로그를 남긴 뒤 기존 하드코딩 값 사용
- Studio 프로세스가 죽어도 tmux 세션과 각 Claude 패널은 영향받지 않음 — Studio는 관찰자 + 선택적 조작자일 뿐 실행 주체가 아님
- LAN 인증 실패 시 401

---

## 테스트 전략

- `test_tmux_control.py`: 실제 tmux 대신 mock subprocess + capture-pane 출력 픽스처로 유닛테스트
- `test_watchdog_loop.py`: 기존 watchdog.sh 검증 시나리오(정체 감지 / 컨텍스트 임계치 / `/clear` 감지)를 동일하게 재현
- `test_api.py`: FastAPI TestClient로 엔드포인트 통합 테스트, 인증 미들웨어(토큰 없음/오답 시 401) 포함

---

## 제외 범위 (v1)

- 외부 인터넷 접근 (추후 과제 — VPN/터널링 등 별도 보안 설계 필요)
- 패널에 텍스트 메시지 전송 UI (기존 Claude 앱으로 처리)
- 권한 승인/거부 응답 UI (기존 Claude 앱으로 처리)
- `claude -p` 헤드리스 호출 기반 LLM 저장 (실제 `/save`와 동일한 합성) — 필요해지면 `wiki_bridge.py`의 저장 함수만 교체
- team.yaml 스키마 자체의 설계/구현 (Track D는 team.yaml이 나오기 전까지 기존 배열에 폴백)
- WebSocket 기반 실시간 푸시 (v1은 폴링으로 충분, 필요시 업그레이드)
