import time

from studio import tmux_control
from studio.pane_state import PaneState, evaluate
from studio.team_config import load_team


class WatchdogState:
    def __init__(self) -> None:
        self.panes: dict[int, dict] = {}
        self._internal: dict[int, PaneState] = {}
        self.stuck_check_enabled: bool = True


STATE = WatchdogState()


def _check_one_pane(idx: int, name: str, state: WatchdogState) -> dict:
    screen = tmux_control.capture_pane(idx)
    prev = state._internal.get(idx, PaneState())
    new_state = evaluate(prev, screen, now=time.time(), stuck_check_enabled=state.stuck_check_enabled)
    state._internal[idx] = new_state

    snapshot = {
        "name": name,
        "stuck": new_state.stuck,
        "last_line": new_state.last_line,
        "context_pct": state.panes.get(idx, {}).get("context_pct"),
        "context_alert": state.panes.get(idx, {}).get("context_alert", False),
    }
    state.panes[idx] = snapshot
    return snapshot


def tick(state: WatchdogState = STATE) -> None:
    """One full polling pass over every pane in the current team roster."""
    for member in load_team():
        _check_one_pane(member["pane"], member["name"], state)


def check_pane_now(idx: int, state: WatchdogState = STATE) -> dict:
    """On-demand single-pane check, independent of stuck_check_enabled.

    The toggle only gates whether `tick()`'s periodic pass *flags* a
    pane as stuck; a manual check always evaluates real elapsed time
    against STUCK_THRESHOLD_SEC so the user can see current status even
    with periodic checking turned off.
    """
    team = {member["pane"]: member["name"] for member in load_team()}
    name = team.get(idx, f"pane-{idx}")

    screen = tmux_control.capture_pane(idx)
    prev = state._internal.get(idx, PaneState())
    new_state = evaluate(prev, screen, now=time.time(), stuck_check_enabled=True)
    state._internal[idx] = new_state

    snapshot = {
        "name": name,
        "stuck": new_state.stuck,
        "last_line": new_state.last_line,
        "context_pct": state.panes.get(idx, {}).get("context_pct"),
        "context_alert": state.panes.get(idx, {}).get("context_alert", False),
    }
    state.panes[idx] = snapshot
    return snapshot
