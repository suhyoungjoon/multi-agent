from unittest.mock import patch

from studio import compact_action

IDLE = '❯ Try "help me debug"'
WORKING = 'Brewed for 12s\n❯ '
CONTEXT_BEFORE = "usage: 40.0k/200k tokens (80.0%)"
CONTEXT_AFTER = "usage: 10.0k/200k tokens (5.0%)"


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_happy_path(mock_send_keys, mock_send_enter, mock_capture, mock_sleep):
    # sequence: pane busy once, then idle (compact done), then /context screen
    mock_capture.side_effect = [WORKING, IDLE, CONTEXT_AFTER]

    result = compact_action.trigger_compact(3)

    assert result == {"ok": True, "before_pct": None, "after_pct": 5.0}
    mock_send_keys.assert_any_call(3, "/compact")
    mock_send_keys.assert_any_call(3, "/context")


@patch("studio.compact_action.time.sleep")
@patch("studio.compact_action.tmux_control.capture_pane")
@patch("studio.compact_action.tmux_control.send_enter")
@patch("studio.compact_action.tmux_control.send_keys")
def test_trigger_compact_times_out_if_never_idle(mock_send_keys, mock_send_enter, mock_capture, mock_sleep):
    mock_capture.return_value = WORKING  # never becomes idle

    result = compact_action.trigger_compact(3)

    assert result == {"ok": False, "reason": "timeout"}
