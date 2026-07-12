from unittest.mock import patch, MagicMock

from studio import tmux_control


def _mock_run(returncode=0, stdout=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


@patch("studio.tmux_control.subprocess.run")
def test_session_exists_true_when_returncode_zero(mock_run):
    mock_run.return_value = _mock_run(returncode=0)
    assert tmux_control.session_exists() is True
    mock_run.assert_called_once_with(
        ["tmux", "has-session", "-t", "team1"],
        capture_output=True,
        check=False,
    )


@patch("studio.tmux_control.subprocess.run")
def test_session_exists_false_when_returncode_nonzero(mock_run):
    mock_run.return_value = _mock_run(returncode=1)
    assert tmux_control.session_exists() is False


@patch("studio.tmux_control.subprocess.run")
def test_capture_pane_returns_stdout(mock_run):
    mock_run.return_value = _mock_run(stdout="❯ Try \"help me debug\"\n")
    output = tmux_control.capture_pane(3)
    assert output == "❯ Try \"help me debug\"\n"
    mock_run.assert_called_once_with(
        ["tmux", "capture-pane", "-t", "team1:0.3", "-p"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("studio.tmux_control.subprocess.run")
def test_send_keys_calls_tmux_send_keys(mock_run):
    mock_run.return_value = _mock_run()
    tmux_control.send_keys(2, "hello")
    mock_run.assert_called_once_with(
        ["tmux", "send-keys", "-t", "team1:0.2", "hello"],
        check=False,
    )


@patch("studio.tmux_control.subprocess.run")
def test_send_enter_calls_tmux_send_keys_enter(mock_run):
    mock_run.return_value = _mock_run()
    tmux_control.send_enter(2)
    mock_run.assert_called_once_with(
        ["tmux", "send-keys", "-t", "team1:0.2", "Enter"],
        check=False,
    )


@patch("studio.tmux_control.subprocess.run")
def test_wake_only_sends_enter(mock_run):
    mock_run.return_value = _mock_run()
    tmux_control.wake(4)
    mock_run.assert_called_once_with(
        ["tmux", "send-keys", "-t", "team1:0.4", "Enter"],
        check=False,
    )


@patch("studio.tmux_control.time.sleep")
@patch("studio.tmux_control.subprocess.run")
def test_reinject_role_sends_text_then_sleeps_then_enter(mock_run, mock_sleep):
    mock_run.return_value = _mock_run()
    tmux_control.reinject_role(1, "너는 민준, 아키텍트야")

    assert mock_run.call_count == 2
    first_call, second_call = mock_run.call_args_list
    assert first_call.args[0] == ["tmux", "send-keys", "-t", "team1:0.1", "너는 민준, 아키텍트야"]
    assert second_call.args[0] == ["tmux", "send-keys", "-t", "team1:0.1", "Enter"]
    mock_sleep.assert_called_once_with(1.5)
