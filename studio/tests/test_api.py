import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["STUDIO_TOKEN"] = "test-token"

from studio.main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-Studio-Token": "test-token"}


def test_status_requires_token():
    response = client.get("/api/status")
    assert response.status_code == 401


@patch("studio.main.watchdog_loop.tick")
def test_status_returns_pane_snapshot(mock_tick):
    response = client.get("/api/status", headers=HEADERS)
    assert response.status_code == 200
    mock_tick.assert_called_once()


def test_watchdog_settings_get_default_enabled():
    response = client.get("/api/watchdog/settings", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"stuck_check_enabled": True}


def test_watchdog_settings_post_toggles_flag():
    response = client.post(
        "/api/watchdog/settings", headers=HEADERS, json={"stuck_check_enabled": False}
    )
    assert response.status_code == 200
    assert response.json() == {"stuck_check_enabled": False}

    get_response = client.get("/api/watchdog/settings", headers=HEADERS)
    assert get_response.json() == {"stuck_check_enabled": False}

    # reset for other tests
    client.post("/api/watchdog/settings", headers=HEADERS, json={"stuck_check_enabled": True})


@patch("studio.main.watchdog_loop.check_pane_now")
def test_pane_check_calls_check_pane_now(mock_check):
    mock_check.return_value = {"name": "쭌", "stuck": False, "last_line": "", "context_pct": None, "context_alert": False}
    response = client.post("/api/pane/0/check", headers=HEADERS)
    assert response.status_code == 200
    mock_check.assert_called_once_with(0)


@patch("studio.main.tmux_control.wake")
def test_pane_wake_calls_tmux_control_wake(mock_wake):
    response = client.post("/api/pane/2/wake", headers=HEADERS)
    assert response.status_code == 200
    mock_wake.assert_called_once_with(2)


@patch("studio.main.tmux_control.reinject_role")
@patch("studio.main.load_roles", return_value={1: "너는 민준이다"})
def test_pane_restart_calls_reinject_role_with_role_text(mock_roles, mock_reinject):
    response = client.post("/api/pane/1/restart", headers=HEADERS)
    assert response.status_code == 200
    mock_reinject.assert_called_once_with(1, "너는 민준이다")


@patch("studio.main.load_roles", return_value={})
def test_pane_restart_returns_404_when_no_role_text(mock_roles):
    response = client.post("/api/pane/9/restart", headers=HEADERS)
    assert response.status_code == 404


@patch("studio.main.compact_action.trigger_compact")
def test_pane_compact_calls_trigger_compact(mock_trigger):
    mock_trigger.return_value = {"ok": True, "before_pct": None, "after_pct": 5.0}
    response = client.post("/api/pane/4/compact", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "before_pct": None, "after_pct": 5.0}
    mock_trigger.assert_called_once_with(4)
