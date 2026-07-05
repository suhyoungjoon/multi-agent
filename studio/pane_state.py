from dataclasses import dataclass, replace

STUCK_THRESHOLD_SEC = 180
_TIMER_WORDS = ("Worked", "Brewed", "Cooked", "Sautéed", "Crunched", "Churned", "Baked")


@dataclass
class PaneState:
    last_hash: object = ""
    last_change_ts: float = 0.0
    stuck: bool = False
    last_line: str = ""


def _last_line(screen_text: str) -> str:
    lines = screen_text.splitlines()
    return lines[-1] if lines else ""


def is_clean_idle(screen_text: str) -> bool:
    """True if the pane is waiting for input with no in-progress timer.

    Mirrors watchdog.sh's is_clean_idle check: last line is the
    placeholder prompt (starts with the idle marker) and none of the
    "Worked for Ns" style timers appear in the recent screen.
    """
    last_line = _last_line(screen_text)
    if not last_line.strip().startswith("❯ Try"):
        return False
    return not any(word in screen_text for word in _TIMER_WORDS)


def evaluate(state: PaneState, screen_text: str, now: float, stuck_check_enabled: bool) -> PaneState:
    """Compute the next PaneState for one polling tick. Never mutates `state`."""
    last_line = _last_line(screen_text)

    if is_clean_idle(screen_text):
        return replace(state, last_hash=hash(screen_text[-400:]), last_change_ts=now, stuck=False, last_line=last_line)

    current_hash = hash(screen_text[-400:])
    if current_hash != state.last_hash:
        return replace(state, last_hash=current_hash, last_change_ts=now, stuck=False, last_line=last_line)

    elapsed = now - state.last_change_ts
    stuck = stuck_check_enabled and elapsed >= STUCK_THRESHOLD_SEC
    return replace(state, last_line=last_line, stuck=stuck)
