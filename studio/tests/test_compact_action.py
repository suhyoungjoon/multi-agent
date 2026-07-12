from unittest.mock import patch

from studio import compact_action

IDLE = '❯ Try "help me debug"'
WORKING = 'Brewed for 12s\n❯ '
CONTEXT_BEFORE = "usage: 40.0k/200k tokens (80.0%)"
CONTEXT_AFTER = "usage: 10.0k/200k tokens (5.0%)"


def test_is_idle_delegates_to_pane_state_is_clean_idle():
    assert compact_action._is_idle(IDLE) is True
    assert compact_action._is_idle(WORKING) is False


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_happy_path(mock_send_keys, mock_send_enter, mock_capture, mock_sleep):
    # sequence: initial /context read, pane busy once, then idle (compact done), then final /context
    mock_capture.side_effect = [CONTEXT_BEFORE, WORKING, IDLE, CONTEXT_AFTER]

    result = compact_action.trigger_compact(3)

    assert result == {"ok": True, "before_pct": 80.0, "after_pct": 5.0}
    mock_send_keys.assert_any_call(3, "/compact")
    mock_send_keys.assert_any_call(3, "/context")


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_before_pct_none_when_initial_context_unparseable(
    mock_send_keys, mock_send_enter, mock_capture, mock_sleep
):
    mock_capture.side_effect = ["no usage line here", WORKING, IDLE, CONTEXT_AFTER]

    result = compact_action.trigger_compact(3)

    assert result == {"ok": True, "before_pct": None, "after_pct": 5.0}


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_after_pct_none_when_final_context_unparseable(
    mock_send_keys, mock_send_enter, mock_capture, mock_sleep
):
    mock_capture.side_effect = [CONTEXT_BEFORE, WORKING, IDLE, "no usage line here"]

    result = compact_action.trigger_compact(3)

    assert result == {"ok": True, "before_pct": 80.0, "after_pct": None}


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_times_out_if_never_idle(mock_send_keys, mock_send_enter, mock_capture, mock_sleep):
    # first call is the initial /context read, then it's WORKING forever
    mock_capture.side_effect = [CONTEXT_BEFORE] + [WORKING] * 40

    result = compact_action.trigger_compact(3)

    assert result == {"ok": False, "reason": "timeout"}
