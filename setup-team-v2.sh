#!/bin/bash
# setup-team.sh — Claude 멀티에이전트 팀 환경 자동 구성 (v2: 병렬 실행 + 견고한 감지)

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SESSION="team1"
WORKDIR="/Users/syj/workspaces/multi-agent"

# Load roster from team.yaml (single source of truth). Falls back to
# the hardcoded roster below if team.yaml is missing/unreadable so a
# config problem never blocks starting the team.
MEMBER_NAMES=()
while IFS= read -r line; do
    MEMBER_NAMES+=("$line")
done < <(python3 -c "
import yaml
try:
    with open('team.yaml') as f:
        data = yaml.safe_load(f)
    for m in sorted(data['team'], key=lambda x: x['pane']):
        print(m['name'])
except Exception:
    pass
" 2>/dev/null)

MEMBER_MODELS=()
while IFS= read -r line; do
    MEMBER_MODELS+=("$line")
done < <(python3 -c "
import yaml
try:
    with open('team.yaml') as f:
        data = yaml.safe_load(f)
    for m in sorted(data['team'], key=lambda x: x['pane']):
        print(m['model'])
except Exception:
    pass
" 2>/dev/null)

if [ "${#MEMBER_NAMES[@]}" -eq 0 ]; then
    MEMBER_NAMES=("쭌" "민준 아키텍트" "지훈 리서쳐" "수아 UI/UX디자이너" "서연 개발자" "태양 QA·리뷰어")
    MEMBER_MODELS=(
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
    )
fi

# ── 유틸: 파인 화면에 패턴이 나타날 때까지 대기 (못 찾아도 실패시키지 않음) ──
wait_for_pane() {
    local pane="$1" pattern="$2" timeout="${3:-15}" waited=0
    while [ $waited -lt $timeout ]; do
        tmux capture-pane -t "$pane" -p 2>/dev/null | grep -qE "$pattern" && return 0
        sleep 1; waited=$((waited + 1))
    done
    return 1
}

# ── 유틸: 모든 파인이 준비됐는지(>나 ❯ 프롬프트가 보이는지) 확인 ──
pane_is_ready() {
    local pane="$1"
    tmux capture-pane -t "$pane" -p 2>/dev/null | tail -5 | grep -qE '(❯|Try ")'
}

# ── [0/4] 사전 요구사항 확인 ────────────────────────────────
echo -e "${YELLOW}[0/4] 사전 요구사항 확인...${NC}"

MISSING=()
command -v tmux   &>/dev/null || MISSING+=("tmux (brew install tmux)")
command -v claude &>/dev/null || MISSING+=("claude (npm install -g @anthropic-ai/claude-code)")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${RED}❌ 누락된 의존성:${NC}"
    for m in "${MISSING[@]}"; do echo "   - $m"; done
    exit 1
fi

if [ ! -d "$WORKDIR" ]; then
    echo -e "${RED}❌ 작업 디렉토리가 존재하지 않습니다: $WORKDIR${NC}"
    exit 1
fi

CLAUDE_BIN="$(command -v claude)"
echo "  ✅ tmux $(tmux -V | awk '{print $2}')"
echo "  ✅ claude $(claude --version 2>/dev/null | head -1)"
echo "  ✅ 작업 디렉토리: $WORKDIR"

# ── [1/4] 기존 세션 정리 ────────────────────────────────────
echo -e "\n${YELLOW}[1/4] 기존 세션 초기화...${NC}"
tmux has-session -t "$SESSION" 2>/dev/null && {
    tmux kill-session -t "$SESSION"
    echo "  기존 '$SESSION' 세션 종료"
}

# ── [2/4] TMUX 세션 & 레이아웃 구성 ────────────────────────
echo -e "\n${YELLOW}[2/4] TMUX 세션 & 레이아웃 구성...${NC}"

TERM_WIDTH=$(tput cols 2>/dev/null || echo 317)
TERM_HEIGHT=$(tput lines 2>/dev/null || echo 85)

tmux new-session -d -s "$SESSION" -x "$TERM_WIDTH" -y "$TERM_HEIGHT" -c "$WORKDIR"

tmux split-window -t "$SESSION:0.0" -h -c "$WORKDIR"
tmux split-window -t "$SESSION:0.1" -h -c "$WORKDIR"
tmux split-window -t "$SESSION:0.2" -h -c "$WORKDIR"
tmux split-window -t "$SESSION:0.3" -h -c "$WORKDIR"
tmux split-window -t "$SESSION:0.4" -h -c "$WORKDIR"

tmux select-layout -t "$SESSION:0" tiled
tmux select-layout -t "$SESSION:0" main-vertical
tmux set-option -t "$SESSION" main-pane-width 158
tmux select-layout -t "$SESSION:0" main-vertical

tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format " #{pane_title} "
tmux set-option -t "$SESSION" allow-rename off

for i in 0 1 2 3 4 5; do
    tmux select-pane -t "$SESSION:0.$i" -T "${MEMBER_NAMES[$i]}"
done

echo "  ✅ 레이아웃 구성 완료 (6 panes)"

# ── [3/4] Claude 병렬 실행 ──────────────────────────────────
echo -e "\n${YELLOW}[3/4] Claude 실행 중 (6개 파인 동시 실행)...${NC}"

# 3-1. 모든 파인에 동시에 claude 실행 명령 전송
for i in 0 1 2 3 4 5; do
    pane="$SESSION:0.$i"
    tmux send-keys -t "$pane" C-c 2>/dev/null
    sleep 0.1
    tmux send-keys -t "$pane" \
        "cd '$WORKDIR' && unset CLAUDECODE && $CLAUDE_BIN --model ${MEMBER_MODELS[$i]} --dangerously-skip-permissions" Enter
done

echo "  모든 파인에 실행 명령 전송 완료. 다이얼로그 처리 대기 중..."
sleep 3

# 3-2. 다이얼로그(폴더 신뢰 / 약관 동의)가 떠 있으면 일괄 처리 — 최대 4회 반복
for round in 1 2 3 4; do
    ANY_DIALOG=0
    for i in 0 1 2 3 4 5; do
        pane="$SESSION:0.$i"
        screen="$(tmux capture-pane -t "$pane" -p 2>/dev/null)"

        if echo "$screen" | grep -qi "trust this folder"; then
            tmux send-keys -t "$pane" Enter
            ANY_DIALOG=1
        elif echo "$screen" | grep -qi "I accept"; then
            tmux send-keys -t "$pane" Down
            sleep 0.3
            tmux send-keys -t "$pane" Enter
            ANY_DIALOG=1
        fi
    done
    [ "$ANY_DIALOG" -eq 0 ] && break
    sleep 2
done

# 3-3. 각 파인이 준비됐는지 최종 확인 (최대 30초 대기)
echo "  파인별 준비 상태 확인 중..."
for i in 0 1 2 3 4 5; do
    pane="$SESSION:0.$i"
    echo -n "  Pane $i (${MEMBER_NAMES[$i]}): "
    waited=0
    while [ $waited -lt 30 ]; do
        pane_is_ready "$pane" && break
        sleep 1; waited=$((waited + 1))
    done
    if pane_is_ready "$pane"; then
        echo -e "${GREEN}✅ 준비 완료${NC}"
    else
        echo -e "${RED}⚠️  확인 필요 (tmux attach 후 직접 확인)${NC}"
    fi
done

# ── [4/4] 완료 ──────────────────────────────────────────────
echo -e "\n${GREEN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ✅ 팀 환경 구성 완료!              ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

[ -t 1 ] && tmux attach -t "$SESSION"
