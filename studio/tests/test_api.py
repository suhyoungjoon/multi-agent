import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["STUDIO_TOKEN"] = "test-token"

from studio import watchdog_loop  # noqa: E402
from studio.main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-Studio-Token": "test-token"}


def test_status_requires_token():
    response = client.get("/api/status")
    assert response.status_code == 401


@patch("studio.main.watchdog_loop.tick")
def test_status_returns_pane_snapshot(mock_tick):
    watchdog_loop.STATE.panes[0] = {
        "name": "쭌", "stuck": False, "last_line": "❯ Try \"help\"", "context_pct": None, "context_alert": False,
    }

    response = client.get("/api/status", headers=HEADERS)

    assert response.status_code == 200
    mock_tick.assert_called_once()
    body = response.json()
    assert "panes" in body
    assert body["panes"]["0"] == {
        "name": "쭌", "stuck": False, "last_line": "❯ Try \"help\"", "context_pct": None, "context_alert": False,
    }
    watchdog_loop.STATE.panes.clear()  # avoid leaking state into other tests


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


def test_wiki_hot_requires_token():
    response = client.get("/api/wiki/hot")
    assert response.status_code == 401


@patch("studio.main.wiki_bridge.read_hot_cache", return_value="# hot cache content")
def test_wiki_hot_returns_content_with_valid_token(mock_read):
    response = client.get("/api/wiki/hot", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"content": "# hot cache content"}


def test_wiki_search_requires_token():
    response = client.get("/api/wiki/search?q=test")
    assert response.status_code == 401


@patch("studio.main.wiki_bridge.search_wiki")
def test_wiki_search_calls_bridge_with_query(mock_search):
    mock_search.return_value = [{"file": "wiki/research/test.md", "snippet": "..."}]
    response = client.get("/api/wiki/search?q=test", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"results": [{"file": "wiki/research/test.md", "snippet": "..."}]}
    mock_search.assert_called_once_with("test")


def test_wiki_save_requires_token():
    response = client.post(
        "/api/wiki/save",
        json={"domain": "studio-notes", "title": "t", "content": "c", "tags": []},
    )
    assert response.status_code == 401


@patch("studio.main.wiki_bridge.save_note")
def test_wiki_save_calls_bridge_and_returns_path(mock_save):
    mock_save.return_value = Path("/vault/wiki/studio-notes/t.md")
    response = client.post(
        "/api/wiki/save",
        headers=HEADERS,
        json={"domain": "studio-notes", "title": "t", "content": "c", "tags": ["studio"]},
    )
    assert response.status_code == 200
    assert response.json() == {"path": "/vault/wiki/studio-notes/t.md"}
    mock_save.assert_called_once_with("studio-notes", "t", "c", ["studio"])
