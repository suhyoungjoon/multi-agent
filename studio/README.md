# Advanced Agent Studio (v1)

로컬 웹 대시보드로 tmux 멀티에이전트 팀(`team1`)의 상태를 보고, 멈춘 패널에 개입하고, wiki 메모리를 조회/저장합니다.

## 설정

```bash
cd ~/workspaces/multi-agent
python3 -m venv .venv   # 이미 있다면 생략
./.venv/bin/pip install -r studio/requirements.txt
cp studio/.env.example studio/.env
python3 -c "import secrets; print(secrets.token_hex(16))"  # 출력값을 studio/.env의 STUDIO_TOKEN에 붙여넣기
```

## 실행

```bash
cd ~/workspaces/multi-agent
STUDIO_TOKEN=$(grep STUDIO_TOKEN studio/.env | cut -d= -f2) \
  ./.venv/bin/python3 -m uvicorn studio.main:app --host 0.0.0.0 --port 8420 --reload
```

- 맥북에서: `http://localhost:8420`
- 같은 LAN의 다른 기기에서: `http://<맥북의 LAN IP>:8420` (예: `ipconfig getifaddr en0`로 확인)
- 접속 시 상단 입력창에 `.env`에 설정한 토큰을 입력하고 "저장" 클릭 (브라우저 localStorage에 저장됨)

## 전제 조건

- `tmux` 세션 `team1`이 `setup-team-v2.sh`로 이미 떠 있어야 `/api/status`가 정상 응답합니다.
- `setup-team-v2.sh`/`watchdog.sh`는 그대로 유지되며, Studio는 이들을 대체하지 않습니다 — 필요시 언제든 기존 방식으로 폴백하세요.

## v1 범위 밖

- 외부 인터넷 접근, 패널에 텍스트 메시지 전송, 권한 승인 UI, LLM 기반 저장(`claude -p`), 패널 kill+재실행.
- `/clear` 감지 시 자동 역할재주입, 컨텍스트 임계치 자동 compact — v1은 정체 감지 + 수동 wake/restart/compact만 지원.

자세한 내용은 `docs/superpowers/specs/2026-07-05-advanced-agent-studio-design.md`와
`docs/superpowers/plans/2026-07-05-advanced-agent-studio.md` 참고.
