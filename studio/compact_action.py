import time

from studio import tmux_control
from studio.context_usage import parse_context_usage

COMPACT_WAIT_TIMEOUT_SEC = 90
COMPACT_POLL_INTERVAL_SEC = 3


def _is_idle(screen_text: str) -> bool:
    lines = screen_text.splitlines()
    last_line = lines[-1] if lines else ""
    return last_line.strip().startswith("❯ Try")


def trigger_compact(idx: int) -> dict:
    """Send /compact, wait for the pane to return to idle, then report /context %.

    Manual, user-triggered only — never called from the background tick.
    """
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

    tmux_control.send_keys(idx, "/context")
    time.sleep(1.5)
    tmux_control.send_enter(idx)
    time.sleep(1.5)

    after_screen = tmux_control.capture_pane(idx)
    parsed = parse_context_usage(after_screen)
    after_pct = parsed[0] if parsed else None

    return {"ok": True, "before_pct": None, "after_pct": after_pct}
