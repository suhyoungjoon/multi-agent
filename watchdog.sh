#!/bin/bash
# watchdog.sh — team1(6패널) 자동 감시 + 안전 조치 + macOS 알림
#
# 요구사항: bash 4+ (declare -A 연관 배열 사용 — macOS 기본 /bin/bash 3.2에서는
# "declare: -A: invalid option" 및 이후 배열 인덱스 연산 오류 발생). 저장소로
# 이동만 됐을 뿐 이 요구사항은 아직 충족되지 않음(2026-07-18 team.yaml 마이그레이션
# 스코프 밖 — MEMBER_NAMES 배열만 team.yaml 연동으로 교체함). 실행 전 `brew install bash`
# 후 `/opt/homebrew/bin/bash watchdog.sh`로 실행 필요.
#
# 사용법:
#   ./watchdog.sh [세션명(기본 team1)] [점검주기초(기본 20)]
#
# 동작:
#   - 입력창에 텍스트만 남고 Enter가 안 눌린 상태   → 자동으로 Enter 재전송
#   - "Do you want to proceed? 1. Yes"류 승인 대기 → 자동으로 1 + Enter
#   - 화면이 STUCK_THRESHOLD(기본 180초) 이상 전혀 안 바뀜 → 알림만 (자동 조치 안 함)
#   - 보고 발신 후 일정 시간 내 수신측에 흔적이 안 보임 → 알림만
#   - 컨텍스트 사용량(패널별 1시간 주기, idle일 때만 점검)
#       · CONTEXT_THRESHOLD(기본 70%) 이상 → 알림만
#       · COMPACT_THRESHOLD(기본 85%) 이상 → 자동 /compact 실행 후 결과 재확인
#       · 토큰이 직전 대비 급감(/clear로 추정) → 역할 지시문 자동 재주입
#
# 종료: Ctrl+C

SESSION="${1:-team1}"
INTERVAL="${2:-20}"
STUCK_THRESHOLD=180   # 이 시간(초) 이상 화면 변화가 없으면 "진짜 멈춤" 알림
RENOTIFY_INTERVAL=600 # 같은 문제가 계속될 때 재알림 주기(초) — 너무 잦은 반복 알림 방지
LOG_FILE="$HOME/.claude-watchdog.log"
SNOOZE_DIR="$HOME/.claude-watchdog-snooze"

# ── 컨텍스트 사용량 점검 설정 ──
CONTEXT_CHECK_INTERVAL_SEC=3600   # 패널별로 60분마다 /context 점검 (idle일 때만)
CONTEXT_THRESHOLD=70              # 이 퍼센트 넘으면 알림만 (자동 조치 없음)
COMPACT_THRESHOLD=85              # 이 퍼센트 넘으면 자동 /compact 실행 (idle일 때만)
COMPACT_MIN_DROP_PCT=10           # 압축 후 이만큼(%p) 안 줄면 "효과 미미" 알림
COMPACT_WAIT_TIMEOUT=90           # /compact 완료 대기 최대 초
CLEAR_DETECTION_FLOOR=20000       # 직전보다 이 토큰 밑으로 급감하면 /clear로 추정
declare -A LAST_CONTEXT_CHECK_TS
declare -A LAST_CONTEXT_TOKENS

mkdir -p "$SNOOZE_DIR"

# ── ack 모드: ./watchdog.sh ack <패널번호> [분(기본10)] 으로 직접 호출하면
#    해당 패널의 알림을 지정 시간 동안 끈다. 워치독 본체와 별개로 즉시 실행되고 종료된다.
if [ "$1" == "ack" ]; then
    PANE_IDX="$2"
    SNOOZE_MIN="${3:-10}"
    if [ -z "$PANE_IDX" ]; then
        echo "사용법: $0 ack <패널번호 0-5> [분(기본10)]"
        exit 1
    fi
    until_ts=$(( $(date +%s) + SNOOZE_MIN * 60 ))
    echo "$until_ts" > "$SNOOZE_DIR/pane_${PANE_IDX}"
    echo "패널 ${PANE_IDX} 알림을 ${SNOOZE_MIN}분간 끕니다 (확인 완료 처리)."
    exit 0
fi

# Load display names from team.yaml (single source of truth — see
# team_config.py / setup-team-v2.sh for the same pattern). Falls back to
# the hardcoded roster if team.yaml is missing or unreadable so the
# watchdog never refuses to start over a config problem.
MEMBER_NAMES=()
while IFS= read -r line; do
    MEMBER_NAMES+=("$line")
done < <(cd "$(dirname "${BASH_SOURCE[0]}")" && python3 -c "
import yaml
try:
    with open('team.yaml') as f:
        data = yaml.safe_load(f)
    for m in sorted(data['team'], key=lambda x: x['pane']):
        print(m['name'])
except Exception:
    pass
" 2>/dev/null)

if [ "${#MEMBER_NAMES[@]}" -eq 0 ]; then
    MEMBER_NAMES=("쭌" "민준" "지훈" "수아" "서연" "태양")
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

declare -A LAST_SNAPSHOT
declare -A LAST_CHANGE_TS
declare -A NOTIFIED_STUCK

notify() {
    local title="$1" message="$2" sound="${3:-Glass}"
    osascript -e "display notification \"${message}\" with title \"${title}\" sound name \"${sound}\"" 2>/dev/null
    echo "[$(date '+%H:%M:%S')] ALERT: ${title} — ${message}" >> "$LOG_FILE"
}

# 패널이 snooze(확인완료) 상태인지 확인. 시간이 지나면 자동 해제.
is_snoozed() {
    local idx="$1"
    local f="$SNOOZE_DIR/pane_${idx}"
    [ -f "$f" ] || return 1
    local until_ts now
    until_ts="$(cat "$f" 2>/dev/null)"
    now=$(date +%s)
    if [ -n "$until_ts" ] && [ "$now" -lt "$until_ts" ]; then
        return 0   # 아직 snooze 중
    else
        rm -f "$f"
        return 1   # 만료됨 → snooze 해제
    fi
}

log() {
    echo -e "$1"
    echo "[$(date '+%H:%M:%S')] $(echo -e "$1" | sed 's/\x1b\[[0-9;]*m//g')" >> "$LOG_FILE"
}

# 역할 메시지를 패널에 재전송 (텍스트/Enter 분리, 전송 패턴은 setup-team-v2.sh와 동일)
reinject_role() {
    local pane="$1" idx="$2" name="$3"
    if [ "$ROLES_LOADED" -ne 1 ] || [ -z "${MEMBER_ROLES[$idx]:-}" ]; then
        notify "역할 재주입 실패: $name" "역할 파일을 찾지 못해 자동 재주입을 못했습니다 — 수동으로 확인해주세요." "Basso"
        log "${RED}[$name] 역할 재주입 실패 — ROLES_LOADED=$ROLES_LOADED${NC}"
        return
    fi
    tmux send-keys -t "$pane" "${MEMBER_ROLES[$idx]}"
    sleep 1.5
    tmux send-keys -t "$pane" Enter
    notify "역할 자동 재주입: $name" "/clear로 추정되는 컨텍스트 초기화를 감지해 역할 지시문을 다시 보냈습니다." "Pop"
    log "${YELLOW}[$name] 역할 재주입 완료${NC}"
}

# 컨텍스트 사용량 점검: idle 상태일 때만 /context 실행 → 퍼센트 파싱 →
# 70%+ 알림, 그리고 직전 대비 토큰이 급감했으면 /clear로 추정해 역할 재주입
# 임계치(COMPACT_THRESHOLD) 초과 시 자동 /compact 실행 → 완료 대기 → /context로 재확인.
# 재확인 시 얻은 토큰 수는 LAST_CONTEXT_TOKENS에 직접 덮어써서, 다음 주기의 /clear 감지(check_context_usage)가
# 우리가 방금 수행한 압축으로 인한 정상적인 토큰 감소를 "/clear로 추정되는 초기화"로 오인하지 않게 한다.
auto_compact_if_needed() {
    local pane="$1" name="$2" idx="$3" pre_pct="$4"
    local last_line waited post_screen post_usage_line post_pct post_used_raw post_used_tokens drop

    if ! awk -v p="$pre_pct" -v t="$COMPACT_THRESHOLD" 'BEGIN{exit !(p>=t)}'; then
        return
    fi

    log "${YELLOW}[$name] 컨텍스트 ${pre_pct}% — 자동 /compact 시도${NC}"
    tmux send-keys -t "$pane" "/compact"
    sleep 1
    tmux send-keys -t "$pane" Enter

    # 압축 완료(=idle 프롬프트 복귀) 대기. 끝나기 전엔 다음 단계로 넘어가지 않는다.
    waited=0
    while [ "$waited" -lt "$COMPACT_WAIT_TIMEOUT" ]; do
        last_line="$(tmux capture-pane -t "$pane" -p 2>/dev/null | tail -1)"
        echo "$last_line" | grep -qE '^❯ Try "' && break
        sleep 3; waited=$((waited + 3))
    done

    if [ "$waited" -ge "$COMPACT_WAIT_TIMEOUT" ]; then
        log "${RED}[$name] /compact 완료 대기 시간 초과(${COMPACT_WAIT_TIMEOUT}초) — 결과 확인 못함${NC}"
        notify "자동 압축 결과 확인 필요: $name" "/compact 실행했지만 ${COMPACT_WAIT_TIMEOUT}초 내 완료 확인 못함 — 패널 직접 확인 필요" "Basso"
        return
    fi

    sleep 1
    tmux send-keys -t "$pane" "/context"
    sleep 1
    tmux send-keys -t "$pane" Enter
    sleep 1.5

    post_screen="$(tmux capture-pane -t "$pane" -p -S -100)"
    post_usage_line="$(echo "$post_screen" | grep -oE '[0-9.]+k?/[0-9.]+k tokens \([0-9.]+%\)' | tail -1)"

    if [ -z "$post_usage_line" ]; then
        log "${RED}[$name] 압축 후 컨텍스트 확인 실패 — 출력 형식 확인 필요${NC}"
        notify "자동 압축 확인 실패: $name" "/compact는 실행됐지만 결과를 파싱하지 못했습니다 — 수동 확인 필요" "Basso"
        return
    fi

    post_pct="$(echo "$post_usage_line" | grep -oE '\([0-9.]+%\)' | tr -d '()%')"
    post_used_raw="$(echo "$post_usage_line" | grep -oE '^[0-9.]+k?')"
    post_used_tokens="$(echo "$post_used_raw" | sed 's/k$//' | awk '{printf "%d", $1*1000}')"

    log "${GREEN}[$name] 자동 압축 완료: ${pre_pct}% → ${post_pct}%${NC}"

    drop="$(awk -v a="$pre_pct" -v b="$post_pct" 'BEGIN{printf "%.1f", a-b}')"
    if awk -v d="$drop" -v m="$COMPACT_MIN_DROP_PCT" 'BEGIN{exit !(d<m)}'; then
        notify "자동 압축 효과 미미: $name" "${pre_pct}% → ${post_pct}% (${drop}%p 감소) — 수동 확인 권장" "Funk"
        log "${YELLOW}[$name] 압축 효과 미미(${drop}%p < ${COMPACT_MIN_DROP_PCT}%p 기준)${NC}"
    fi

    # 압축 직후 값을 baseline으로 확정 — /clear 오탐 방지 (위 주석 참고)
    LAST_CONTEXT_TOKENS[$idx]="$post_used_tokens"
}

check_context_usage() {
    local pane="$1" name="$2" idx="$3"
    local pre_screen last_line post_screen usage_line pct used_raw used_tokens prev_tokens

    pre_screen="$(tmux capture-pane -t "$pane" -p)"
    last_line="$(echo "$pre_screen" | tail -1)"

    # 작업 중(idle이 아님)이면 끼어들지 않고 다음 주기에 다시 시도
    if ! echo "$last_line" | grep -qE '^❯ Try "'; then
        return
    fi

    tmux send-keys -t "$pane" "/context"
    sleep 1
    tmux send-keys -t "$pane" Enter
    sleep 1.5

    post_screen="$(tmux capture-pane -t "$pane" -p -S -100)"
    usage_line="$(echo "$post_screen" | grep -oE '[0-9.]+k?/[0-9.]+k tokens \([0-9.]+%\)' | head -1)"

    if [ -z "$usage_line" ]; then
        log "${YELLOW}[$name] 컨텍스트 사용량 파싱 실패 — 출력 형식 확인 필요${NC}"
        return
    fi

    pct="$(echo "$usage_line" | grep -oE '\([0-9.]+%\)' | tr -d '()%')"
    used_raw="$(echo "$usage_line" | grep -oE '^[0-9.]+k?')"
    used_tokens="$(echo "$used_raw" | sed 's/k$//' | awk '{printf "%d", $1*1000}')"

    log "${CYAN}[$name] 컨텍스트 사용량: ${pct}% (${usage_line})${NC}"

    # ── /clear로 추정되는 급격한 초기화 감지 ──
    prev_tokens="${LAST_CONTEXT_TOKENS[$idx]:-0}"
    if [ "$prev_tokens" -gt "$CLEAR_DETECTION_FLOOR" ] && [ "$used_tokens" -lt "$CLEAR_DETECTION_FLOOR" ]; then
        log "${YELLOW}[$name] /clear로 추정되는 컨텍스트 초기화 감지 (${prev_tokens} → ${used_tokens} tokens) → 역할 재주입${NC}"
        reinject_role "$pane" "$idx" "$name"
    fi
    LAST_CONTEXT_TOKENS[$idx]="$used_tokens"

    # ── 임계치 초과 알림 (snooze 중이면 조용히 통과 — ack 명령 재사용) ──
    if awk -v p="$pct" -v t="$CONTEXT_THRESHOLD" 'BEGIN{exit !(p>=t)}'; then
        if ! is_snoozed "$idx"; then
            notify "컨텍스트 임계치 초과: $name" "${pct}% 사용 중 — /compact 권장 (확인했다면: watchdog.sh ack $idx)" "Funk"
        fi
    fi

    # ── 더 높은 임계치(COMPACT_THRESHOLD)를 넘으면 알림에 그치지 않고 자동 압축 ──
    auto_compact_if_needed "$pane" "$name" "$idx" "$pct"
}

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo -e "${RED}세션 '$SESSION'을 찾을 수 없습니다.${NC}"
    exit 1
fi

# ── WORKDIR 자동 감지 (pane 0의 실제 작업 디렉토리 기준) + 역할 메시지 파일 로드 ──
# setup-team-v2.sh가 내보낸 .claude-team-roles.sh를 읽어 MEMBER_ROLES 배열을 복원한다.
# /clear로 추정되는 컨텍스트 초기화 감지 시 이 배열로 역할을 자동 재주입한다.
WORKDIR="$(tmux display-message -p -t "${SESSION}:0.0" '#{pane_current_path}' 2>/dev/null)"
ROLES_FILE="${WORKDIR}/.claude-team-roles.sh"
if [ -n "$WORKDIR" ] && [ -f "$ROLES_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ROLES_FILE"
    ROLES_LOADED=1
else
    ROLES_LOADED=0
fi

log "${CYAN}워치독 시작 — 세션: $SESSION, 점검 주기: ${INTERVAL}초${NC}"
if [ "$ROLES_LOADED" -eq 1 ]; then
    log "${GREEN}역할 메시지 로드 완료 — /clear 자동 재주입 활성화${NC}"
else
    log "${YELLOW}역할 메시지 파일을 찾지 못함(${ROLES_FILE}) — /clear 자동 재주입 비활성화${NC}"
fi
notify "워치독 시작" "$SESSION 세션 감시를 시작합니다." "Pop"

for i in 0 1 2 3 4 5; do
    LAST_SNAPSHOT[$i]=""
    LAST_CHANGE_TS[$i]=$(date +%s)
    NOTIFIED_STUCK[$i]=0
    LAST_CONTEXT_CHECK_TS[$i]=$(date +%s)
    LAST_CONTEXT_TOKENS[$i]=0
done

while true; do
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        notify "워치독 중단" "$SESSION 세션이 더 이상 존재하지 않습니다." "Basso"
        log "${RED}세션이 사라짐. 워치독 종료.${NC}"
        exit 1
    fi

    for i in 0 1 2 3 4 5; do
        pane="$SESSION:0.$i"
        name="${MEMBER_NAMES[$i]}"
        screen="$(tmux capture-pane -t "$pane" -p 2>/dev/null)"
        tail5="$(echo "$screen" | tail -5)"
        last_line="$(echo "$screen" | tail -1)"

        # ── 1. 권한 승인 대기 감지 → 자동 승인 ──────────────────
        if echo "$tail5" | grep -qE "Do you want to proceed\?|requires approval"; then
            tmux send-keys -t "$pane" "1"
            sleep 0.5
            tmux send-keys -t "$pane" Enter
            log "${YELLOW}[$name] 권한 승인 대기 감지 → 자동 승인(1+Enter) 처리${NC}"
            sleep 1
            continue
        fi

        # ── 2. trust folder / 약관 동의 등 onboarding 다이얼로그 ──
        if echo "$tail5" | grep -qi "trust this folder"; then
            tmux send-keys -t "$pane" Enter
            log "${YELLOW}[$name] trust folder 다이얼로그 감지 → Enter 자동 처리${NC}"
            sleep 1
            continue
        fi
        if echo "$tail5" | grep -qi "I accept"; then
            tmux send-keys -t "$pane" Down
            sleep 0.3
            tmux send-keys -t "$pane" Enter
            log "${YELLOW}[$name] 약관 동의 다이얼로그 감지 → 자동 처리${NC}"
            sleep 1
            continue
        fi

        # ── 3. 입력창에 텍스트만 남고 전송 안 된 상태 감지 ────────
        # 마지막 줄이 "❯ <내용>" 형태이고, 그 바로 다음에 프롬프트 박스(bypass permissions 등)가
        # 이어지는 일반적인 "대기중" 모양과 다르게, 같은 내용이 두 주기 연속 그대로면 전송 실패로 간주
        if echo "$last_line" | grep -qE '^❯ .{3,}'; then
            content="${last_line#❯ }"
            # 흔한 기본 placeholder는 제외
            if [[ "$content" != *'Try "'* ]]; then
                if [ "${LAST_SNAPSHOT[$i]}_INPUT" == "${content}_INPUT" ]; then
                    tmux send-keys -t "$pane" Enter
                    log "${YELLOW}[$name] 입력창 정체(Enter 누락 의심) 감지 → Enter 자동 재전송${NC}"
                    sleep 1
                    continue
                fi
                LAST_SNAPSHOT[$i]="${content}_INPUT"
            fi
        fi

        # ── 4. 화면 자체가 오래 안 바뀌는 "진짜 멈춤" 감지 (정상 idle 대기와 구분) ──
        current_hash="$(echo "$screen" | tail -8 | md5 2>/dev/null || echo "$screen" | tail -8 | md5sum)"

        # 정상 idle 판단: 마지막 줄이 placeholder 프롬프트(예: ❯ Try "...")이고
        # 작업중 표시(Worked/Brewed/Cooked 등 타이머)가 화면에 없으면, 단순히 할 일이 없어
        # 다음 지시를 기다리는 정상 대기 상태로 간주한다.
        is_clean_idle=0
        if echo "$last_line" | grep -qE '^❯ Try "'; then
            if ! echo "$tail5" | grep -qE '(Worked|Brewed|Cooked|Sautéed|Crunched|Churned|Baked) for [0-9]+'; then
                is_clean_idle=1
            fi
        fi

        if [ "$is_clean_idle" -eq 1 ]; then
            # 정상 대기 상태 — 타이머만 리셋하고 알림 대상에서 제외
            LAST_SNAPSHOT[${i}_hash]="$current_hash"
            LAST_CHANGE_TS[$i]=$(date +%s)
            NOTIFIED_STUCK[$i]=0
        elif [ "${LAST_SNAPSHOT[${i}_hash]}" != "$current_hash" ]; then
            LAST_SNAPSHOT[${i}_hash]="$current_hash"
            LAST_CHANGE_TS[$i]=$(date +%s)
            NOTIFIED_STUCK[$i]=0
        else
            now=$(date +%s)
            elapsed=$(( now - LAST_CHANGE_TS[$i] ))
            last_notified="${NOTIFIED_STUCK[$i]:-0}"

            if [ "$elapsed" -ge "$STUCK_THRESHOLD" ]; then
                if is_snoozed "$i"; then
                    : # 사용자가 ack로 확인 완료 처리함 — 조용히 통과
                elif [ "$last_notified" -eq 0 ] || [ $(( now - last_notified )) -ge "$RENOTIFY_INTERVAL" ]; then
                    if echo "$tail5" | grep -qE '(Worked|Brewed|Cooked|Sautéed|Crunched|Churned|Baked) for [0-9]+'; then
                        reason="작업 진행 표시가 ${elapsed}초간 멈춰있음 (응답 없음 의심)"
                    else
                        reason="${elapsed}초간 비정상 화면 상태 지속 (입력 대기/오류 가능성)"
                    fi
                    reason="${reason} — 확인했다면: watchdog.sh ack $i"
                    notify "패널 정체 의심: $name" "$reason" "Basso"
                    log "${RED}[$name] $reason${NC}"
                    NOTIFIED_STUCK[$i]=$now
                fi
            fi
        fi

        # ── 5. 컨텍스트 사용량 점검 (패널별 1시간 주기, idle일 때만) ──
        now_ctx=$(date +%s)
        if [ $(( now_ctx - ${LAST_CONTEXT_CHECK_TS[$i]:-0} )) -ge "$CONTEXT_CHECK_INTERVAL_SEC" ]; then
            check_context_usage "$pane" "$name" "$i"
            LAST_CONTEXT_CHECK_TS[$i]=$now_ctx
        fi
    done

    sleep "$INTERVAL"
done
