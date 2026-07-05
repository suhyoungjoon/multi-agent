from unittest.mock import patch

from studio import watchdog_loop
from studio.pane_state import PaneState


def _team_fixture():
    return [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준", "model": "claude-sonnet-4-6"},
    ]


@patch("studio.watchdog_loop.load_team", return_value=_team_fixture())
@patch("studio.watchdog_loop.tmux_control.capture_pane")
def test_tick_updates_state_for_every_pane(mock_capture, mock_team):
    mock_capture.return_value = '❯ Try "help"'
    state = watchdog_loop.WatchdogState()

    watchdog_loop.tick(state=state)

    assert set(state.panes.keys()) == {0, 1}
    assert state.panes[0]["name"] == "쭌"
    assert state.panes[0]["stuck"] is False


@patch("studio.watchdog_loop.load_team", return_value=_team_fixture())
@patch("studio.watchdog_loop.tmux_control.capture_pane")
def test_tick_marks_pane_stuck_after_repeated_unchanged_ticks(mock_capture, mock_team):
    mock_capture.return_value = "frozen screen\n❯ "
    state = watchdog_loop.WatchdogState()
    state.panes[0] = {
        "name": "쭌", "stuck": False, "last_line": "", "context_pct": None, "context_alert": False,
    }
    state._internal[0] = PaneState(
        last_hash=hash("frozen screen\n❯ "[-400:]),
        last_change_ts=0.0,
        stuck=False,
    )
    state._internal[1] = PaneState()

    with patch("studio.watchdog_loop.time.time", return_value=181.0):
        watchdog_loop.tick(state=state)

    assert state.panes[0]["stuck"] is True


@patch("studio.watchdog_loop.load_team", return_value=_team_fixture())
@patch("studio.watchdog_loop.tmux_control.capture_pane")
def test_tick_skips_stuck_flagging_when_toggle_disabled(mock_capture, mock_team):
    mock_capture.return_value = "frozen screen\n❯ "
    state = watchdog_loop.WatchdogState()
    state.stuck_check_enabled = False
    state._internal[0] = PaneState(
        last_hash=hash("frozen screen\n❯ "[-400:]),
        last_change_ts=0.0,
        stuck=False,
    )
    state._internal[1] = PaneState()

    with patch("studio.watchdog_loop.time.time", return_value=500.0):
        watchdog_loop.tick(state=state)

    assert state.panes[0]["stuck"] is False


@patch("studio.watchdog_loop.load_team", return_value=_team_fixture())
@patch("studio.watchdog_loop.tmux_control.capture_pane")
def test_check_pane_now_works_even_when_toggle_disabled(mock_capture, mock_team):
    mock_capture.return_value = "frozen screen\n❯ "
    state = watchdog_loop.WatchdogState()
    state.stuck_check_enabled = False
    state._internal[0] = PaneState(
        last_hash=hash("frozen screen\n❯ "[-400:]),
        last_change_ts=0.0,
        stuck=False,
    )

    with patch("studio.watchdog_loop.time.time", return_value=999.0):
        result = watchdog_loop.check_pane_now(0, state=state)

    assert result["stuck"] is True
    assert state.panes[0]["stuck"] is True
