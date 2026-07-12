import time

from studio import tmux_control
from studio.context_usage import parse_context_usage
from studio.pane_state import is_clean_idle

COMPACT_WAIT_TIMEOUT_SEC = 90
COMPACT_POLL_INTERVAL_SEC = 3


def _is_idle(screen_text: str) -> bool:
    """Delegates to pane_state.is_clean_idle so compact-wait and stuck-detection
    share a single definition of "idle" and can't drift apart."""
    return is_clean_idle(screen_text)


def _read_context_pct(idx: int) -> float | None:
    tmux_control.send_keys(idx, "/context")
    time.sleep(1.5)
    tmux_control.send_enter(idx)
    time.sleep(1.5)

    screen = tmux_control.capture_pane(idx)
    parsed = parse_context_usage(screen)
    return parsed[0] if parsed else None


def trigger_compact(idx: int) -> dict:
    """Send /compact, wait for the pane to return to idle, then report /context %
    from before and after the compaction.

    Manual, user-triggered only — never called from the background tick.
    """
    before_pct = _read_context_pct(idx)

    tmux_control.send_keys(idx, "/compact")
    time.sleep(1)
    tmux_control.send_enter(idx)

    waited = 0
    while waited < COMPACT_WAIT_TIMEOUT_SEC:
        screen = tmux_control.capture_pane(idx)
        if _is_idle(screen):
            break
        time.sleep(COMPACT_POLL_INTERVAL_SEC)
        waited += COMPACT_POLL_INTERVAL_SEC
    else:
        return {"ok": False, "reason": "timeout"}

    after_pct = _read_context_pct(idx)

    return {"ok": True, "before_pct": before_pct, "after_pct": after_pct}
