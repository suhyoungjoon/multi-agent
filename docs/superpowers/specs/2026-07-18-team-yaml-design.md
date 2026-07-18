# team.yaml — 팀 구성 추상화 (Track A) 설계 문서

> 작성: Claude | 날짜: 2026-07-18
> 상태: 승인됨

---

## 개요

현재 팀 로스터/역할/보고체계/산출물 정보가 4곳(`setup-team-v2.sh`, `watchdog.sh`, `CLAUDE.md`, `studio/roles.yaml`)에 중복·분산되어 있다. `team.yaml`을 단일 소스로 만들어 각 소비자가 이를 읽도록 마이그레이션한다.

- **범위**: 로스터(이름/pane/모델) + 역할 텍스트 + 보고체계 + 산출물 경로만 통합. Pane 시작 시 역할 메시지 자동 주입(현재 존재하지 않는 기능)은 이번 스코프 밖 — 별도 과제
- **owns_files**: ADR-004의 memory_store 데모 한정 값(서연=store.py 등)이라 team.yaml에는 빈 배열로 시작, 프로젝트별로 사람이 직접 채우는 필드로 둠(영구적 사실이 아님)

---

## `team.yaml` 스키마

저장소 루트(`~/workspaces/multi-agent/team.yaml`)에 신규 생성:

```yaml
team:
  - name: 쭌
    pane: 0
    model: claude-sonnet-4-6
    role: |
      너는 쭌, 팀장(Orchestrator)이다. 직접 작업 금지 — 지시 수령 → 팀원 배분 → 결과 보고.
    reports_to: null
    outputs: []
    hub_for: []
    owns_files: []

  - name: 민준
    pane: 1
    model: claude-sonnet-4-6
    role: |
      너는 민준, 아키텍트다. 아키텍처/API 설계 및 설계 문서 작성을 담당한다.
      지훈·서연·태양 사이의 보고 허브 역할을 한다.
    reports_to: 쭌
    outputs: [docs/architecture.md, docs/api-spec.md, docs/data-model.md]
    hub_for: [지훈, 서연, 태양]
    owns_files: []

  - name: 지훈
    pane: 2
    model: claude-sonnet-4-6
    role: |
      너는 지훈, 리서쳐다. 기술 트렌드/라이브러리 조사, 경쟁 서비스 분석을 담당한다.
      결과는 민준에게만 보고한다.
    reports_to: 민준
    outputs: [docs/research/]
    hub_for: []
    owns_files: []

  - name: 수아
    pane: 3
    model: claude-sonnet-4-6
    role: |
      너는 수아, UI/UX 디자이너다. 사용자 흐름 및 컴포넌트 설계, CLI/프론트엔드 구현을 담당한다.
    reports_to: 쭌
    outputs: [docs/design/]
    hub_for: []
    owns_files: []

  - name: 서연
    pane: 4
    model: claude-sonnet-4-6
    role: |
      너는 서연, 개발자다. 백엔드·핵심 로직(API 서버/DB 스키마/유닛테스트)을 전담한다.
    reports_to: 민준
    outputs: []
    hub_for: []
    owns_files: []

  - name: 태양
    pane: 5
    model: claude-sonnet-4-6
    role: |
      너는 태양, QA 리뷰어다. 버그/보안/성능/가독성 4관점으로 리뷰한다.
      결과는 민준에게 보고한다.
    reports_to: 민준
    outputs: [docs/review/]
    hub_for: []
    owns_files: []
```

필드 의미:
- `pane`: tmux pane 인덱스(0-5) — 배열 채울 때 이 값 기준 정렬
- `role`: 역할 재주입/자기판단용 텍스트 (기존 `studio/roles.yaml`의 내용을 그대로 이전)
- `reports_to`: 직접 보고 대상 (`null`이면 사용자에게 직접 보고)
- `hub_for`: 이 사람에게 보고가 수렴하는 하위 인원 목록 (민준만 해당)
- `outputs`, `owns_files`: 산출물 경로 / 파일 소유권(프로젝트별로 채워지는 선택 필드)

---

## 소비자별 마이그레이션

### `setup-team-v2.sh`

```bash
readarray -t MEMBER_NAMES < <(python3 -c "
import yaml
with open('team.yaml') as f:
    data = yaml.safe_load(f)
for m in sorted(data['team'], key=lambda x: x['pane']):
    print(m['name'])
" 2>/dev/null)

readarray -t MEMBER_MODELS < <(python3 -c "
import yaml
with open('team.yaml') as f:
    data = yaml.safe_load(f)
for m in sorted(data['team'], key=lambda x: x['pane']):
    print(m['model'])
" 2>/dev/null)

if [ "${#MEMBER_NAMES[@]}" -eq 0 ]; then
    MEMBER_NAMES=("쭌" "민준 아키텍트" "지훈 리서쳐" "수아 UI/UX디자이너" "서연 개발자" "태양 QA·리뷰어")
    MEMBER_MODELS=("claude-sonnet-4-6" "claude-sonnet-4-6" "claude-sonnet-4-6" "claude-sonnet-4-6" "claude-sonnet-4-6" "claude-sonnet-4-6")
fi
```

기존 하드코딩 배열 리터럴을 대체. 나머지 로직(tmux 세션 생성, 다이얼로그 처리, 준비 상태 확인)은 변경 없음 — 배열이 채워지는 소스만 바뀜.

### `watchdog.sh`

동일한 패턴으로 알림표시용 `MEMBER_NAMES` 배열만 교체. `reinject_role()`이 참조하는 `.claude-team-roles.sh` 관련 로직은 이번 스코프 밖(이미 존재하지 않는 파일이라 원래도 죽은 코드 — Studio의 `roles.py`가 이 문제를 별도로 이미 해결함).

### `studio/team_config.py`

3단 폴백으로 재작성:
```python
def load_team(yaml_path=DEFAULT_YAML_PATH, script_path=DEFAULT_SCRIPT_PATH) -> list[dict]:
    # 1순위: team.yaml
    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and data.get("team"):
            return sorted(data["team"], key=lambda m: m["pane"])
    except (OSError, yaml.YAMLError):
        pass
    # 2순위: setup-team-v2.sh 배열 파싱 (기존 로직 그대로 유지)
    ...
    # 3순위: 하드코딩 (기존 _fallback_team() 그대로 유지)
```

### `studio/roles.py`

`team.yaml`의 `role` 필드를 pane 인덱스로 매핑해 반환하도록 재작성. `studio/roles.yaml` 파일은 삭제(내용은 이미 위 스키마에 그대로 옮겨졌으므로 데이터 유실 없음). `load_roles() -> dict[int, str]` 시그니처는 유지 — `main.py`의 `restart_pane()` 호출부는 변경 불필요.

### `CLAUDE.md`

로스터 표 + 보고체계 다이어그램 섹션을 "정확한 팀 구성/역할/보고체계는 `team.yaml` 참고"로 축약. tmux 3단계 전송 규칙, wiki vault 섹션은 프로세스 설명(데이터가 아님)이므로 그대로 유지.

---

## 에러 처리

- `team.yaml`이 없거나 YAML 파싱 실패 → 각 소비자는 조용히 다음 폴백 단계로 이동 (Hook들과 동일한 "절대 팀 작업을 막지 않는다" 원칙)
- `team.yaml`에 `pane` 중복/누락 → 정렬 시 순서가 예측 불가해질 수 있음. 이번 라운드에서는 검증 로직 없이 사람이 직접 주의(향후 필요시 검증 스크립트 추가 검토)

---

## 검증 방법

- `studio/team_config.py`, `studio/roles.py`의 team.yaml 읽기 경로: 기존 pytest 컨벤션으로 커버(임시 team.yaml 픽스처로 파싱 결과 검증, team.yaml 없을 때 폴백 동작 검증)
- `setup-team-v2.sh`/`watchdog.sh`: 원래도 pytest 대상이 아닌 인터랙티브 launcher. python3 파싱 스니펫만 독립적으로 실행해 `MEMBER_NAMES`/`MEMBER_MODELS` 배열이 team.yaml 내용과 일치하는지 수동 확인
- 실제 `setup-team-v2.sh` 실행까지는 이번 스코프에서 필수 아님(팀 재기동은 리스크 있는 작업이라, 스크립트 변경이 배열 채우는 부분에 국한된다는 걸 코드 리뷰+수동 스니펫 검증으로 충분히 확인 가능하다고 판단)

---

## 제외 범위

- **Pane 시작 시 역할 메시지 자동 주입** — 현재 `setup-team-v2.sh`는 pane을 띄우기만 하고 "너는 OOO야" 메시지를 보내지 않음(발견된 기존 갭). 이번 설계는 이 갭을 고치지 않고, `team.yaml`이 그 데이터 소스가 될 준비만 해둠. 별도 스펙으로 분리
- **`team.yaml` 스키마 검증 로직** — 중복 pane, 잘못된 reports_to 참조 등에 대한 자동 검증은 범위 밖
- **watchdog.sh의 `reinject_role()`/`.claude-team-roles.sh` 의존성 수정** — 이미 죽은 코드였고 Studio가 별도로 우회했으므로 이번 스코프에서 다루지 않음
