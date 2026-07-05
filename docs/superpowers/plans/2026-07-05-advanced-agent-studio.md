# Advanced Agent Studio v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI web dashboard (`studio/`) that shows live status of the 6-pane tmux multi-agent team, lets the user manually wake/reinject-role/compact a pane, and reads/writes the `multi-agent-wiki` vault — without touching the existing `setup-team-v2.sh` / `watchdog.sh` scripts.

**Architecture:** Single FastAPI process serves both a JSON API and a static frontend. A background asyncio task ports `watchdog.sh`'s detection logic (stuck-screen check, `/clear`-reset detection, context-usage polling, auto-compact) into pure Python functions that call `tmux` via `subprocess`. All destructive-feeling actions (wake, role reinject, compact) are exposed as POST endpoints the user triggers manually from the UI — none of them auto-fire except the two watchdog already auto-fires today (`/clear` reinject, auto-compact past threshold).

**Tech Stack:** Python 3.13, FastAPI 0.117, uvicorn, PyYAML, python-dotenv, pytest + httpx (TestClient), vanilla JS frontend (no build step).

## Global Constraints

- Read the spec first: `docs/superpowers/specs/2026-07-05-advanced-agent-studio-design.md` — every task below implements a section of it.
- Do not modify or delete `setup-team-v2.sh` or `watchdog.sh`. Studio is additive; those scripts remain the fallback.
- All tmux interaction goes through `studio/tmux_control.py` — no other module calls `subprocess` with `tmux` directly.
- All new code lives under `studio/`. Tests live under `studio/tests/`.
- Run tests with: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/ -v`
- tmux session name is always `"team1"`, pane path format is `f"team1:0.{idx}"` — matches `setup-team-v2.sh`/`watchdog.sh` exactly.
- Every commit uses `git add <exact files>` (never `git add -A` or `git add .`).

---

### Task 1: Project scaffolding + health check

**Files:**
- Create: `studio/__init__.py` (empty)
- Create: `studio/requirements.txt`
- Create: `studio/main.py`
- Test: `studio/tests/test_main.py`

**Interfaces:**
- Produces: `studio/main.py` exposes a module-level `app` (FastAPI instance) that later tasks import and extend with more routes.

- [ ] **Step 1: Create the package init and requirements files**

`studio/__init__.py`:
```python
```
(empty file — makes `studio` an importable package)

`studio/requirements.txt`:
```
fastapi==0.117.1
uvicorn==0.34.0
pyyaml==6.0.2
python-dotenv==1.0.1
pytest==9.1.1
httpx==0.28.1
```

- [ ] **Step 2: Write the failing test**

`studio/tests/test_main.py`:
```python
from fastapi.testclient import TestClient

from studio.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.main'`

- [ ] **Step 4: Write minimal implementation**

`studio/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="Advanced Agent Studio")


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_main.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/__init__.py studio/requirements.txt studio/main.py studio/tests/test_main.py
git commit -m "feat(studio): scaffold FastAPI app with health check"
```

---

### Task 2: tmux_control.py — pane primitives

**Files:**
- Create: `studio/tmux_control.py`
- Test: `studio/tests/test_tmux_control.py`

**Interfaces:**
- Produces:
  - `SESSION: str = "team1"`
  - `session_exists(session: str = SESSION) -> bool`
  - `capture_pane(idx: int, session: str = SESSION) -> str`
  - `send_keys(idx: int, text: str, session: str = SESSION) -> None`
  - `send_enter(idx: int, session: str = SESSION) -> None`
  - `wake(idx: int, session: str = SESSION) -> None`
  - `reinject_role(idx: int, role_text: str, session: str = SESSION) -> None`

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_tmux_control.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_tmux_control.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.tmux_control'`

- [ ] **Step 3: Write minimal implementation**

`studio/tmux_control.py`:
```python
import subprocess
import time

SESSION = "team1"


def _pane_target(idx: int, session: str = SESSION) -> str:
    return f"{session}:0.{idx}"


def session_exists(session: str = SESSION) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def capture_pane(idx: int, session: str = SESSION) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", _pane_target(idx, session), "-p"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def send_keys(idx: int, text: str, session: str = SESSION) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", _pane_target(idx, session), text],
        check=False,
    )


def send_enter(idx: int, session: str = SESSION) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", _pane_target(idx, session), "Enter"],
        check=False,
    )


def wake(idx: int, session: str = SESSION) -> None:
    """Resend Enter only — lightweight nudge for a genuinely stuck pane.

    Never called automatically; only ever triggered by a user clicking
    the wake button after checking pane status.
    """
    send_enter(idx, session)


def reinject_role(idx: int, role_text: str, session: str = SESSION) -> None:
    """Resend a pane's role instruction: text, sleep 1.5s, Enter.

    Mirrors watchdog.sh's reinject_role() 3-step send pattern exactly —
    tmux drops input if text and Enter are sent in the same call.
    """
    send_keys(idx, role_text, session)
    time.sleep(1.5)
    send_enter(idx, session)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_tmux_control.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/tmux_control.py studio/tests/test_tmux_control.py
git commit -m "feat(studio): add tmux_control pane primitives"
```

---

### Task 3: team_config.py — team roster loader with fallback

**Files:**
- Create: `studio/team_config.py`
- Test: `studio/tests/test_team_config.py`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces:
  - `DEFAULT_SCRIPT_PATH: Path` (points at `../setup-team-v2.sh` relative to `studio/`)
  - `load_team(script_path: Path = DEFAULT_SCRIPT_PATH) -> list[dict]` — each dict has keys `pane: int`, `name: str`, `model: str`

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_team_config.py`:
```python
from pathlib import Path

from studio import team_config

FIXTURE_SCRIPT = '''#!/bin/bash
MEMBER_NAMES=("쭌" "민준 아키텍트" "지훈 리서쳐")
MEMBER_MODELS=(
    "claude-sonnet-4-6"
    "claude-sonnet-4-6"
    "claude-opus-4-8"
)
'''


def test_load_team_parses_names_and_models(tmp_path: Path):
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(script)

    assert team == [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준 아키텍트", "model": "claude-sonnet-4-6"},
        {"pane": 2, "name": "지훈 리서쳐", "model": "claude-opus-4-8"},
    ]


def test_load_team_falls_back_when_script_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist.sh"

    team = team_config.load_team(missing)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"
    assert all("model" in member for member in team)


def test_load_team_falls_back_when_arrays_absent(tmp_path: Path):
    script = tmp_path / "empty.sh"
    script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

    team = team_config.load_team(script)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_team_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.team_config'`

- [ ] **Step 3: Write minimal implementation**

`studio/team_config.py`:
```python
import re
from pathlib import Path

DEFAULT_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "setup-team-v2.sh"

_FALLBACK_NAMES = ["쭌", "민준 아키텍트", "지훈 리서쳐", "수아 UI/UX디자이너", "서연 개발자", "태양 QA·리뷰어"]
_FALLBACK_MODEL = "claude-sonnet-4-6"


def _extract_array(script_text: str, var_name: str) -> list[str]:
    match = re.search(rf'{var_name}=\((.*?)\)', script_text, re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]*)"', match.group(1))


def _fallback_team() -> list[dict]:
    return [
        {"pane": idx, "name": name, "model": _FALLBACK_MODEL}
        for idx, name in enumerate(_FALLBACK_NAMES)
    ]


def load_team(script_path: Path = DEFAULT_SCRIPT_PATH) -> list[dict]:
    """Load the team roster from setup-team-v2.sh's bash arrays.

    Falls back to the hardcoded 6-member roster if the script is
    missing, unreadable, or doesn't define MEMBER_NAMES — this is the
    team.yaml placeholder until that schema exists (see spec §team_config.py).
    """
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return _fallback_team()

    names = _extract_array(text, "MEMBER_NAMES")
    if not names:
        return _fallback_team()

    models = _extract_array(text, "MEMBER_MODELS")
    team = []
    for idx, name in enumerate(names):
        model = models[idx] if idx < len(models) else _FALLBACK_MODEL
        team.append({"pane": idx, "name": name, "model": model})
    return team
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_team_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/team_config.py studio/tests/test_team_config.py
git commit -m "feat(studio): add team_config loader with setup-team-v2.sh fallback parsing"
```

---

### Task 4: roles.yaml + roles.py loader

**Files:**
- Create: `studio/roles.yaml`
- Create: `studio/roles.py`
- Test: `studio/tests/test_roles.py`

**Interfaces:**
- Produces: `DEFAULT_ROLES_PATH: Path`, `load_roles(path: Path = DEFAULT_ROLES_PATH) -> dict[int, str]` (pane index -> role instruction text)

- [ ] **Step 1: Write the actual roles.yaml content**

`studio/roles.yaml`:
```yaml
0: |
  너는 쭌, 팀장(Orchestrator)이다. 직접 작업 금지 — 지시 수령 → 팀원 배분 → 결과 보고.
1: |
  너는 민준, 아키텍트다. 아키텍처/API 설계 및 설계 문서 작성을 담당한다.
  지훈·서연·태양 사이의 보고 허브 역할을 한다.
2: |
  너는 지훈, 리서쳐다. 기술 트렌드/라이브러리 조사, 경쟁 서비스 분석을 담당한다.
  결과는 민준에게만 보고한다.
3: |
  너는 수아, UI/UX 디자이너다. 사용자 흐름 및 컴포넌트 설계, CLI/프론트엔드 구현을 담당한다.
4: |
  너는 서연, 개발자다. 백엔드·핵심 로직(API 서버/DB 스키마/유닛테스트)을 전담한다.
5: |
  너는 태양, QA 리뷰어다. 버그/보안/성능/가독성 4관점으로 리뷰한다.
  결과는 민준에게 보고한다.
```

- [ ] **Step 2: Write the failing tests**

`studio/tests/test_roles.py`:
```python
from pathlib import Path

from studio import roles

FIXTURE_YAML = """
0: |
  너는 쭌, 팀장이다.
1: |
  너는 민준, 아키텍트다.
"""


def test_load_roles_parses_pane_index_to_text(tmp_path: Path):
    roles_file = tmp_path / "roles.yaml"
    roles_file.write_text(FIXTURE_YAML, encoding="utf-8")

    loaded = roles.load_roles(roles_file)

    assert loaded[0] == "너는 쭌, 팀장이다.\n"
    assert loaded[1] == "너는 민준, 아키텍트다.\n"


def test_load_roles_returns_empty_dict_when_file_missing(tmp_path: Path):
    missing = tmp_path / "nope.yaml"

    loaded = roles.load_roles(missing)

    assert loaded == {}


def test_default_roles_yaml_has_six_entries():
    loaded = roles.load_roles()

    assert set(loaded.keys()) == {0, 1, 2, 3, 4, 5}
    assert "쭌" in loaded[0]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_roles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.roles'`

- [ ] **Step 4: Write minimal implementation**

`studio/roles.py`:
```python
from pathlib import Path

import yaml

DEFAULT_ROLES_PATH = Path(__file__).resolve().parent / "roles.yaml"


def load_roles(path: Path = DEFAULT_ROLES_PATH) -> dict[int, str]:
    """Load pane-index -> role-instruction-text mapping from roles.yaml.

    Returns an empty dict if the file is missing, rather than raising —
    callers (watchdog_loop) treat an empty dict as "role reinject
    unavailable for this pane" and skip the reinject with a logged
    warning instead of crashing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    raw = yaml.safe_load(text) or {}
    return {int(idx): value for idx, value in raw.items()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_roles.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/roles.yaml studio/roles.py studio/tests/test_roles.py
git commit -m "feat(studio): add roles.yaml as Studio's own role-text source"
```

---

### Task 5: pane_state.py — stuck-detection logic + toggle

**Files:**
- Create: `studio/pane_state.py`
- Test: `studio/tests/test_pane_state.py`

**Interfaces:**
- Consumes: nothing from prior tasks (pure logic module).
- Produces:
  - `STUCK_THRESHOLD_SEC: int = 180`
  - `@dataclass PaneState` with fields: `last_hash: str = ""`, `last_change_ts: float = 0.0`, `stuck: bool = False`, `last_line: str = ""`
  - `is_clean_idle(screen_text: str) -> bool`
  - `evaluate(state: PaneState, screen_text: str, now: float, stuck_check_enabled: bool) -> PaneState` — returns a **new** `PaneState` (does not mutate the input)

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_pane_state.py`:
```python
from studio.pane_state import PaneState, STUCK_THRESHOLD_SEC, evaluate, is_clean_idle

IDLE_SCREEN = 'some earlier output\n❯ Try "help me debug"'
WORKING_SCREEN = 'Brewed for 12s\n❯ '
UNCHANGED_SCREEN = "same output every tick\n❯ "


def test_is_clean_idle_true_for_placeholder_prompt_without_timer():
    assert is_clean_idle(IDLE_SCREEN) is True


def test_is_clean_idle_false_when_timer_word_present():
    assert is_clean_idle(WORKING_SCREEN) is False


def test_evaluate_resets_timer_on_clean_idle():
    state = PaneState(last_hash="x", last_change_ts=0.0, stuck=True)
    new_state = evaluate(state, IDLE_SCREEN, now=1000.0, stuck_check_enabled=True)
    assert new_state.stuck is False
    assert new_state.last_change_ts == 1000.0


def test_evaluate_marks_stuck_after_threshold_when_screen_unchanged():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC + 1
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=True)
    assert new_state.stuck is True


def test_evaluate_does_not_mark_stuck_before_threshold():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC - 1
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=True)
    assert new_state.stuck is False


def test_evaluate_never_marks_stuck_when_toggle_disabled():
    state = PaneState(last_hash=hash(UNCHANGED_SCREEN[-400:]), last_change_ts=0.0, stuck=False)
    now = STUCK_THRESHOLD_SEC + 100
    new_state = evaluate(state, UNCHANGED_SCREEN, now=float(now), stuck_check_enabled=False)
    assert new_state.stuck is False


def test_evaluate_resets_timer_when_screen_changes():
    state = PaneState(last_hash=hash("old screen"), last_change_ts=0.0, stuck=False)
    new_state = evaluate(state, "brand new screen content\n❯ ", now=50.0, stuck_check_enabled=True)
    assert new_state.last_change_ts == 50.0
    assert new_state.stuck is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_pane_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.pane_state'`

- [ ] **Step 3: Write minimal implementation**

`studio/pane_state.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_pane_state.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/pane_state.py studio/tests/test_pane_state.py
git commit -m "feat(studio): add pane_state stuck-detection logic with toggle support"
```

---

### Task 6: context_usage.py — parse `/context` output

**Files:**
- Create: `studio/context_usage.py`
- Test: `studio/tests/test_context_usage.py`

**Interfaces:**
- Produces:
  - `CONTEXT_THRESHOLD_PCT: float = 70.0`
  - `COMPACT_THRESHOLD_PCT: float = 85.0`
  - `CLEAR_DETECTION_FLOOR: int = 20000`
  - `parse_context_usage(screen_text: str) -> tuple[float, int] | None` — returns `(pct, used_tokens)` or `None` if no usage line found

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_context_usage.py`:
```python
from studio.context_usage import parse_context_usage

SCREEN_WITH_K = "some header\n12.3k/200k tokens (45.2%)\nfooter"
SCREEN_WITHOUT_K = "some header\n800/200k tokens (0.4%)\nfooter"
SCREEN_NO_USAGE = "nothing relevant here"


def test_parse_context_usage_with_k_suffix():
    result = parse_context_usage(SCREEN_WITH_K)
    assert result == (45.2, 12300)


def test_parse_context_usage_without_k_suffix():
    result = parse_context_usage(SCREEN_WITHOUT_K)
    assert result == (0.4, 800)


def test_parse_context_usage_returns_none_when_not_found():
    assert parse_context_usage(SCREEN_NO_USAGE) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_context_usage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.context_usage'`

- [ ] **Step 3: Write minimal implementation**

`studio/context_usage.py`:
```python
import re

CONTEXT_THRESHOLD_PCT = 70.0
COMPACT_THRESHOLD_PCT = 85.0
CLEAR_DETECTION_FLOOR = 20000

_USAGE_RE = re.compile(r'([\d.]+)(k?)/[\d.]+k?\s*tokens\s*\(([\d.]+)%\)')


def parse_context_usage(screen_text: str) -> tuple[float, int] | None:
    """Parse a `/context` screen for (percent_used, used_tokens).

    Mirrors watchdog.sh's grep -oE pipeline for
    '[0-9.]+k?/[0-9.]+k tokens ([0-9.]+%)'. Returns None if the pattern
    isn't present (e.g. /context hasn't finished rendering yet).
    """
    match = _USAGE_RE.search(screen_text)
    if not match:
        return None
    raw_amount, k_suffix, pct = match.groups()
    used_tokens = float(raw_amount) * 1000 if k_suffix == "k" else float(raw_amount)
    return float(pct), int(used_tokens)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_context_usage.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/context_usage.py studio/tests/test_context_usage.py
git commit -m "feat(studio): add context_usage parser for /context screens"
```

---

### Task 7: watchdog_loop.py — background tick integrating detection + auto-actions

**Files:**
- Create: `studio/watchdog_loop.py`
- Test: `studio/tests/test_watchdog_loop.py`

**Interfaces:**
- Consumes:
  - `studio.tmux_control.capture_pane`, `send_keys`, `send_enter`, `reinject_role`
  - `studio.pane_state.PaneState`, `evaluate`
  - `studio.context_usage.parse_context_usage`, `CONTEXT_THRESHOLD_PCT`, `COMPACT_THRESHOLD_PCT`, `CLEAR_DETECTION_FLOOR`
  - `studio.roles.load_roles`
  - `studio.team_config.load_team`
- Produces:
  - `class WatchdogState` — holds `panes: dict[int, dict]` (JSON-serializable snapshot per pane: `name`, `stuck`, `last_line`, `context_pct`, `context_alert`), `stuck_check_enabled: bool = True`
  - `STATE = WatchdogState()` (module-level singleton the API layer reads)
  - `def tick() -> None` — one full synchronous pass over all panes, updates `STATE`
  - `def check_pane_now(idx: int) -> dict` — on-demand single-pane check, independent of `stuck_check_enabled`, returns the pane's status dict and also updates `STATE.panes[idx]`

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_watchdog_loop.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_watchdog_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.watchdog_loop'`

- [ ] **Step 3: Write minimal implementation**

`studio/watchdog_loop.py`:
```python
import time

from studio import tmux_control
from studio.pane_state import PaneState, evaluate
from studio.roles import load_roles
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_watchdog_loop.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/watchdog_loop.py studio/tests/test_watchdog_loop.py
git commit -m "feat(studio): add watchdog_loop tick + on-demand pane check"
```

> **Scope note:** this task only implements stuck-detection. The **automatic** versions of `/clear`-drop role-reinject and context%-threshold auto-compact firing unattended inside `tick()` (the two behaviors the spec says "stay automatic regardless of the toggle") are **not implemented in this plan** — they require driving a multi-second `/context`/`/compact` interaction sequence unattended on a timer, which is materially riskier to get right than the rest of v1. Ship v1 with stuck-detection + manual wake/restart/compact (Task 7b) first; add the automatic-firing versions as a fast-follow task once the manual paths are proven in daily use. This narrows Task 7's original spec scope — flag this trade-off to the user before executing. **This does not affect the manual, user-clicked `/api/pane/{idx}/compact` endpoint** — that one is a required v1 feature and is implemented next, in Task 7b.

---

### Task 7b: compact_action.py — manual compact trigger

**Files:**
- Create: `studio/compact_action.py`
- Test: `studio/tests/test_compact_action.py`

**Interfaces:**
- Consumes: `studio.tmux_control.send_keys`, `send_enter`, `capture_pane`; `studio.context_usage.parse_context_usage`.
- Produces: `COMPACT_WAIT_TIMEOUT_SEC: int = 90`, `COMPACT_POLL_INTERVAL_SEC: int = 3`, `trigger_compact(idx: int) -> dict` — returns `{"ok": True, "before_pct": float|None, "after_pct": float|None}` on success, or `{"ok": False, "reason": "timeout"}` if the pane never returns to idle within the timeout.

This is a manual, one-shot action the user clicks — distinct from the deferred *automatic* compact-on-threshold behavior in Task 7. It sends `/compact`, waits for the pane to return to its idle prompt, then re-reads `/context` to report the before/after percentage.

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_compact_action.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_compact_action.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.compact_action'`

- [ ] **Step 3: Write minimal implementation**

`studio/compact_action.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_compact_action.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/compact_action.py studio/tests/test_compact_action.py
git commit -m "feat(studio): add manual compact_action trigger (user-clicked, not automatic)"
```

---

### Task 8: auth.py — LAN token authentication

**Files:**
- Create: `studio/auth.py`
- Create: `studio/.env.example`
- Test: `studio/tests/test_auth.py`

**Interfaces:**
- Produces: `require_token(x_studio_token: str = Header(default="")) -> None` (FastAPI dependency; raises `HTTPException(401)` on mismatch), reads expected token from `STUDIO_TOKEN` env var via `python-dotenv`.

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_auth.py`:
```python
import pytest
from fastapi import HTTPException

from studio import auth


def test_require_token_raises_401_when_missing(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_token(x_studio_token="")
    assert exc_info.value.status_code == 401


def test_require_token_raises_401_when_wrong(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_token(x_studio_token="wrong")
    assert exc_info.value.status_code == 401


def test_require_token_passes_when_correct(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    auth.require_token(x_studio_token="secret123")  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.auth'`

- [ ] **Step 3: Write minimal implementation**

`studio/.env.example`:
```
# Copy to studio/.env and set a real random token before running Studio.
# Generate one with: python3 -c "import secrets; print(secrets.token_hex(16))"
STUDIO_TOKEN=changeme
```

`studio/auth.py`:
```python
import os

from fastapi import Header, HTTPException


def require_token(x_studio_token: str = Header(default="")) -> None:
    """FastAPI dependency guarding every /api route from LAN access.

    Reads STUDIO_TOKEN fresh from the environment on every call (not
    cached at import time) so tests can monkeypatch it per-case.
    """
    expected = os.environ.get("STUDIO_TOKEN", "")
    if not expected or x_studio_token != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-Studio-Token header")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_auth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/auth.py studio/.env.example studio/tests/test_auth.py
git commit -m "feat(studio): add LAN token auth dependency"
```

---

### Task 9: wiki_bridge.py — hot cache read, search, template save

**Files:**
- Create: `studio/wiki_bridge.py`
- Test: `studio/tests/test_wiki_bridge.py`

**Interfaces:**
- Produces:
  - `DEFAULT_VAULT_PATH: Path` (points at `~/workspaces/multi-agent-wiki`)
  - `read_hot_cache(vault_path: Path = DEFAULT_VAULT_PATH) -> str`
  - `search_wiki(query: str, vault_path: Path = DEFAULT_VAULT_PATH) -> list[dict]` — each hit is `{"file": str, "snippet": str}`
  - `save_note(domain: str, title: str, content: str, tags: list[str], vault_path: Path = DEFAULT_VAULT_PATH) -> Path` — writes `wiki/<domain>/<title-slug>.md` with a frontmatter template, returns the written path

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_wiki_bridge.py`:
```python
from pathlib import Path

from studio import wiki_bridge


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "hot.md").write_text("# Recent Context\n\nsomething about memory_store", encoding="utf-8")
    (vault / "wiki" / "research").mkdir()
    (vault / "wiki" / "research" / "claude-certification.md").write_text(
        "CCA-F certification details here", encoding="utf-8"
    )
    return vault


def test_read_hot_cache_returns_file_contents(tmp_path: Path):
    vault = _make_vault(tmp_path)
    content = wiki_bridge.read_hot_cache(vault)
    assert "Recent Context" in content


def test_read_hot_cache_returns_empty_string_when_missing(tmp_path: Path):
    vault = tmp_path / "empty_vault"
    vault.mkdir()
    assert wiki_bridge.read_hot_cache(vault) == ""


def test_search_wiki_finds_matching_file(tmp_path: Path):
    vault = _make_vault(tmp_path)
    results = wiki_bridge.search_wiki("certification", vault_path=vault)
    assert len(results) == 1
    assert "claude-certification.md" in results[0]["file"]
    assert "CCA-F" in results[0]["snippet"]


def test_search_wiki_returns_empty_list_when_no_match(tmp_path: Path):
    vault = _make_vault(tmp_path)
    results = wiki_bridge.search_wiki("nonexistent-term-xyz", vault_path=vault)
    assert results == []


def test_save_note_writes_frontmatter_template(tmp_path: Path):
    vault = _make_vault(tmp_path)
    written = wiki_bridge.save_note(
        domain="studio-notes",
        title="테스트 노트",
        content="본문 내용입니다.",
        tags=["studio", "test"],
        vault_path=vault,
    )
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert 'title: "테스트 노트"' in text
    assert "본문 내용입니다." in text
    assert "- studio" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_wiki_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.wiki_bridge'`

- [ ] **Step 3: Write minimal implementation**

`studio/wiki_bridge.py`:
```python
import datetime
import re
from pathlib import Path

DEFAULT_VAULT_PATH = Path.home() / "workspaces" / "multi-agent-wiki"


def read_hot_cache(vault_path: Path = DEFAULT_VAULT_PATH) -> str:
    hot_file = vault_path / "wiki" / "hot.md"
    try:
        return hot_file.read_text(encoding="utf-8")
    except OSError:
        return ""


def search_wiki(query: str, vault_path: Path = DEFAULT_VAULT_PATH) -> list[dict]:
    wiki_dir = vault_path / "wiki"
    if not wiki_dir.exists():
        return []

    results = []
    query_lower = query.lower()
    for md_file in wiki_dir.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if query_lower not in text.lower():
            continue
        idx = text.lower().index(query_lower)
        start = max(0, idx - 40)
        end = min(len(text), idx + len(query) + 40)
        results.append({"file": str(md_file.relative_to(vault_path)), "snippet": text[start:end]})
    return results


def _slugify(title: str) -> str:
    slug = re.sub(r"\s+", "-", title.strip())
    slug = re.sub(r"[^\w\-가-힣]", "", slug)
    return slug or "untitled"


def save_note(
    domain: str,
    title: str,
    content: str,
    tags: list[str],
    vault_path: Path = DEFAULT_VAULT_PATH,
) -> Path:
    """Write a plain frontmatter-templated note. No LLM synthesis (v1 scope)."""
    domain_dir = vault_path / "wiki" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    tags_yaml = "\n".join(f"  - {tag}" for tag in tags)
    body = f'''---
type: note
title: "{title}"
updated: {today}
tags:
{tags_yaml}
status: current
---

# {title}

{content}
'''
    target = domain_dir / f"{_slugify(title)}.md"
    target.write_text(body, encoding="utf-8")
    return target
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_wiki_bridge.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/wiki_bridge.py studio/tests/test_wiki_bridge.py
git commit -m "feat(studio): add wiki_bridge hot-cache/search/template-save"
```

---

### Task 10: Wire API routes into main.py

**Files:**
- Modify: `studio/main.py`
- Test: `studio/tests/test_api.py`

**Interfaces:**
- Consumes: everything from Tasks 2–9 (`tmux_control`, `team_config`, `roles`, `watchdog_loop.STATE`/`tick`/`check_pane_now`, `compact_action.trigger_compact`, `auth.require_token`, `wiki_bridge`).
- Produces: the full v1 route set, all guarded by `Depends(require_token)`.

- [ ] **Step 1: Write the failing tests**

`studio/tests/test_api.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_api.py -v`
Expected: FAIL — routes don't exist yet (404s where 200s/401s expected)

- [ ] **Step 3: Write the implementation**

`studio/main.py` (full replacement):
```python
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from studio import compact_action, tmux_control, watchdog_loop, wiki_bridge
from studio.auth import require_token
from studio.roles import load_roles

app = FastAPI(title="Advanced Agent Studio")


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/status", dependencies=[Depends(require_token)])
def get_status() -> dict:
    watchdog_loop.tick()
    return {"panes": watchdog_loop.STATE.panes}


class WatchdogSettings(BaseModel):
    stuck_check_enabled: bool


@app.get("/api/watchdog/settings", dependencies=[Depends(require_token)])
def get_watchdog_settings() -> dict:
    return {"stuck_check_enabled": watchdog_loop.STATE.stuck_check_enabled}


@app.post("/api/watchdog/settings", dependencies=[Depends(require_token)])
def set_watchdog_settings(settings: WatchdogSettings) -> dict:
    watchdog_loop.STATE.stuck_check_enabled = settings.stuck_check_enabled
    return {"stuck_check_enabled": watchdog_loop.STATE.stuck_check_enabled}


@app.post("/api/pane/{idx}/check", dependencies=[Depends(require_token)])
def check_pane(idx: int) -> dict:
    return watchdog_loop.check_pane_now(idx)


@app.post("/api/pane/{idx}/wake", dependencies=[Depends(require_token)])
def wake_pane(idx: int) -> dict:
    tmux_control.wake(idx)
    return {"ok": True}


@app.post("/api/pane/{idx}/restart", dependencies=[Depends(require_token)])
def restart_pane(idx: int) -> dict:
    role_text = load_roles().get(idx)
    if role_text is None:
        raise HTTPException(status_code=404, detail=f"no role text defined for pane {idx} in roles.yaml")
    tmux_control.reinject_role(idx, role_text)
    return {"ok": True}


@app.post("/api/pane/{idx}/compact", dependencies=[Depends(require_token)])
def compact_pane(idx: int) -> dict:
    return compact_action.trigger_compact(idx)


@app.get("/api/wiki/hot", dependencies=[Depends(require_token)])
def get_hot_cache() -> dict:
    return {"content": wiki_bridge.read_hot_cache()}


@app.get("/api/wiki/search", dependencies=[Depends(require_token)])
def get_wiki_search(q: str) -> dict:
    return {"results": wiki_bridge.search_wiki(q)}


class SaveNoteRequest(BaseModel):
    domain: str
    title: str
    content: str
    tags: list[str] = []


@app.post("/api/wiki/save", dependencies=[Depends(require_token)])
def post_wiki_save(req: SaveNoteRequest) -> dict:
    path = wiki_bridge.save_note(req.domain, req.title, req.content, req.tags)
    return {"path": str(path)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/test_api.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/ -v`
Expected: PASS (all tests across all modules, ~47 tests)

- [ ] **Step 6: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/main.py studio/tests/test_api.py
git commit -m "feat(studio): wire status/watchdog/pane-action/wiki API routes"
```

---

### Task 11: Minimal frontend + run instructions

**Files:**
- Create: `studio/static/index.html`
- Create: `studio/static/app.js`
- Modify: `studio/main.py` (mount static files)
- Create: `studio/README.md`

**Interfaces:**
- Consumes: all `/api/*` routes from Task 10.
- Produces: a browsable dashboard at `GET /`.

- [ ] **Step 1: Mount static files in main.py**

Add the imports to the top of `studio/main.py`, alongside the existing imports:
```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles
```

Then append this to the **very end** of `studio/main.py`, after every `@app.get`/`@app.post` route defined so far:
```python
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

**This order is required, not stylistic.** Starlette matches routes in registration order and a `Mount("/")` matches every path. If `app.mount("/", ...)` is registered *before* the `/api/...` routes, it will swallow every request — including `/api/health` — before the API routes ever get a chance to match, breaking the entire API. Registering the mount last means Starlette tries each specific `/api/...` route first and only falls through to the static-file mount for everything else.

- [ ] **Step 2: Write the dashboard HTML**

`studio/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Advanced Agent Studio</title>
  <style>
    body { font-family: -apple-system, sans-serif; margin: 2rem; background: #0a0a0a; color: #eee; }
    .pane-card { border: 1px solid #333; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
    .pane-card.stuck { border-color: #d9534f; }
    button { margin-right: 0.5rem; cursor: pointer; }
    #token-input { width: 20rem; }
  </style>
</head>
<body>
  <h1>Advanced Agent Studio</h1>
  <p>
    Token: <input id="token-input" type="password" placeholder="X-Studio-Token">
    <button id="save-token">저장</button>
    <label><input type="checkbox" id="stuck-toggle"> 정체 감지 켜짐</label>
  </p>
  <div id="panes"></div>

  <h2>메모리 (wiki)</h2>
  <pre id="hot-cache" style="white-space: pre-wrap; border: 1px solid #333; padding: 1rem;"></pre>

  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write the polling frontend script**

`studio/static/app.js`:
```javascript
function getToken() {
  return localStorage.getItem("studioToken") || "";
}

document.getElementById("save-token").addEventListener("click", () => {
  const value = document.getElementById("token-input").value;
  localStorage.setItem("studioToken", value);
});

async function apiGet(path) {
  const res = await fetch(path, { headers: { "X-Studio-Token": getToken() } });
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "X-Studio-Token": getToken(), "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

function renderPanes(panes) {
  const container = document.getElementById("panes");
  container.innerHTML = "";
  for (const [idx, pane] of Object.entries(panes)) {
    const card = document.createElement("div");
    card.className = "pane-card" + (pane.stuck ? " stuck" : "");
    card.innerHTML = `
      <strong>${pane.name}</strong> (pane ${idx}) — ${pane.stuck ? "STUCK" : "정상"}<br>
      <code>${(pane.last_line || "").slice(0, 80)}</code><br>
      <button data-action="check" data-idx="${idx}">지금 확인</button>
      <button data-action="wake" data-idx="${idx}">깨우기</button>
      <button data-action="restart" data-idx="${idx}">역할 재주입</button>
      <button data-action="compact" data-idx="${idx}">compact</button>
    `;
    container.appendChild(card);
  }
}

document.getElementById("panes").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  await apiPost(`/api/pane/${button.dataset.idx}/${button.dataset.action}`);
  refreshStatus();
});

document.getElementById("stuck-toggle").addEventListener("change", async (event) => {
  await apiPost("/api/watchdog/settings", { stuck_check_enabled: event.target.checked });
});

async function refreshStatus() {
  const status = await apiGet("/api/status");
  renderPanes(status.panes || {});
  const settings = await apiGet("/api/watchdog/settings");
  document.getElementById("stuck-toggle").checked = settings.stuck_check_enabled;
}

async function refreshHotCache() {
  const hot = await apiGet("/api/wiki/hot");
  document.getElementById("hot-cache").textContent = hot.content || "(hot cache 없음)";
}

refreshStatus();
refreshHotCache();
setInterval(refreshStatus, 2500);
setInterval(refreshHotCache, 10000);
```

- [ ] **Step 4: Write the README**

`studio/README.md`:
```markdown
# Advanced Agent Studio (v1)

로컬 웹 대시보드로 tmux 멀티에이전트 팀(`team1`)의 상태를 보고, 멈춘 패널에 개입하고, wiki 메모리를 조회/저장합니다.

## 설정

```bash
cd studio
pip install -r requirements.txt
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(16))"  # 출력값을 .env의 STUDIO_TOKEN에 붙여넣기
```

## 실행

```bash
cd ~/workspaces/multi-agent
python3 -m uvicorn studio.main:app --host 0.0.0.0 --port 8420 --reload
```

- 맥북에서: `http://localhost:8420`
- 같은 LAN의 다른 기기에서: `http://<맥북의 LAN IP>:8420` (예: `ipconfig getifaddr en0`로 확인)
- 접속 시 상단 입력창에 `.env`에 설정한 토큰을 입력하고 "저장" 클릭 (브라우저 localStorage에 저장됨)

## 전제 조건

- `tmux` 세션 `team1`이 `setup-team-v2.sh`로 이미 떠 있어야 `/api/status`가 정상 응답합니다.
- `setup-team-v2.sh`/`watchdog.sh`는 그대로 유지되며, Studio는 이들을 대체하지 않습니다 — 필요시 언제든 기존 방식으로 폴백하세요.

## v1 범위 밖

- 외부 인터넷 접근, 패널에 텍스트 메시지 전송, 권한 승인 UI, LLM 기반 저장(`claude -p`), 패널 kill+재실행.
  자세한 내용은 `docs/superpowers/specs/2026-07-05-advanced-agent-studio-design.md` 참고.
```

- [ ] **Step 5: Manual smoke test** (no automated test for static frontend rendering — this is the one step in the plan that isn't unit-testable)

Run: `cd ~/workspaces/multi-agent && STUDIO_TOKEN=smoketest python3 -m uvicorn studio.main:app --port 8420 &`
Then: `curl -s http://localhost:8420/api/health`
Expected: `{"status":"ok"}`
Then: `curl -s -H "X-Studio-Token: smoketest" http://localhost:8420/api/watchdog/settings`
Expected: `{"stuck_check_enabled":true}`
Open `http://localhost:8420` in a browser, confirm the page loads without console errors.
Stop the server: `kill %1`

- [ ] **Step 6: Run the full test suite one more time**

Run: `cd ~/workspaces/multi-agent && python3 -m pytest studio/tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
cd ~/workspaces/multi-agent
git add studio/static/index.html studio/static/app.js studio/main.py studio/README.md
git commit -m "feat(studio): add minimal polling dashboard frontend + README"
```

---

## Explicitly deferred to v2 (do not implement now)

- `/clear`-drop auto role-reinject and context%-threshold auto-compact running inside `watchdog_loop.tick()` (see Task 7's scope note).
- External internet access / tunneling.
- Text-message-to-pane and permission-approval UI (handled by the existing Claude app).
- `claude -p` headless LLM-synthesized save.
- Pane kill + relaunch ("확실한 깨우기").
- team.yaml schema (Track A work, not Track D).
