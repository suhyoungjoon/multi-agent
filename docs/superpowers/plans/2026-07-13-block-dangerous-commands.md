# 위험 명령 차단 (Track C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `PreToolUse` hook that blocks (exit 2) known-dangerous Bash commands (`rm -rf`, `git push --force`, direct push to main/master, `.env` exposure) before they execute, with a macOS desktop notification and a log entry per block.

**Architecture:** A standalone bash script (`.claude/hooks/block-dangerous-bash.sh`) reads the PreToolUse JSON payload from stdin, extracts `tool_input.command`, and checks it against 4 regex patterns adapted from an already-verified precedent script (`~/workspaces/claude-code-understanding/.claude/hooks/block-dangerous-bash.sh`). `.claude/settings.json` (already exists with the Track B `Stop` hook) gets a new `PreToolUse` entry added alongside it — not replacing anything.

**Tech Stack:** bash, python3 (JSON parsing only, same pattern as `check-team-progress.sh`), pytest (subprocess-based tests, matching `test_check_team_progress.py`'s convention), `osascript` (macOS notifications).

## Global Constraints

- Read the spec first: `docs/superpowers/specs/2026-07-13-dangerous-command-blocking-design.md` — every task below implements a section of it.
- PreToolUse uses an **exit-code protocol**, not JSON: exit 2 blocks the tool call (stderr becomes the block reason shown to Claude), exit 0 allows it. This is different from the Track B Stop hook's `{"decision":"block",...}` JSON protocol — do not confuse the two.
- The exit-2-blocking mechanism itself is not new territory: it was already live-verified in the precedent project (`claude-code-understanding`, commit `d93fb14`, 태양 approved). This plan does not need to re-derive whether exit 2 works — only verify it wires correctly into *this* repo's shared `.claude/settings.json` alongside the existing Stop hook.
- Do not modify `.claude/hooks/check-team-progress.sh` or the existing `Stop` entry in `.claude/settings.json` — this plan only adds a new `PreToolUse` entry to the same file.
- Every test that could reach the `block()` function must redirect `$HOME` to a `tmp_path` fixture — never let a test write to the real `~/.claude-blocked-commands.log` or trigger a real desktop notification on the developer's machine.
- Run tests with: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_block_dangerous_bash.py -v`

---

### Task 1: `block-dangerous-bash.sh` — blocking script + tests

**Files:**
- Create: `.claude/hooks/block-dangerous-bash.sh`
- Test: `test_block_dangerous_bash.py` (repo root, alongside `test_check_team_progress.py`)

**Interfaces:**
- Produces: an executable script at `.claude/hooks/block-dangerous-bash.sh` that reads a JSON payload of the shape `{"tool_input": {"command": "<the pending bash command>"}}` from stdin. Exits 2 (with a human-readable reason on stderr, a log line appended to `$HOME/.claude-blocked-commands.log`, and a best-effort `osascript` notification) if the command matches a dangerous pattern. Exits 0 otherwise, including when stdin is empty or not valid JSON.

- [ ] **Step 1: Write the failing tests**

`test_block_dangerous_bash.py`:
```python
import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / ".claude" / "hooks" / "block-dangerous-bash.sh"


def _run_hook(command: str, tmp_path: Path, extra_path: str | None = None) -> subprocess.CompletedProcess:
    """Run the hook with a PreToolUse-shaped payload on stdin. $HOME is always
    redirected to tmp_path so tests never touch the real log file or fire a
    real desktop notification."""
    payload = json.dumps({"tool_input": {"command": command}})
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    if extra_path:
        env["PATH"] = f"{extra_path}:{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT)], input=payload, capture_output=True, text=True, env=env
    )


def test_blocks_rm_rf(tmp_path):
    result = _run_hook("rm -rf /tmp/some-dir", tmp_path)
    assert result.returncode == 2
    assert "rm -rf" in result.stderr.lower() or "recursive" in result.stderr.lower()


def test_blocks_rm_fr_variant(tmp_path):
    result = _run_hook("rm -fr /tmp/some-dir", tmp_path)
    assert result.returncode == 2


def test_blocks_sudo_rm_rf(tmp_path):
    result = _run_hook("sudo rm -rf /", tmp_path)
    assert result.returncode == 2


def test_blocks_git_push_force(tmp_path):
    result = _run_hook("git push origin feature/foo --force", tmp_path)
    assert result.returncode == 2


def test_blocks_git_push_dash_f(tmp_path):
    result = _run_hook("git push -f origin feature/foo", tmp_path)
    assert result.returncode == 2


def test_blocks_git_push_origin_main(tmp_path):
    result = _run_hook("git push origin main", tmp_path)
    assert result.returncode == 2


def test_blocks_git_push_origin_master(tmp_path):
    result = _run_hook("git push origin master", tmp_path)
    assert result.returncode == 2


def test_blocks_env_file_read(tmp_path):
    result = _run_hook("cat .env", tmp_path)
    assert result.returncode == 2


def test_allows_safe_ls_command(tmp_path):
    result = _run_hook("ls -la", tmp_path)
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_git_status(tmp_path):
    result = _run_hook("git status", tmp_path)
    assert result.returncode == 0


def test_allows_push_to_feature_branch(tmp_path):
    result = _run_hook("git push origin feature/my-branch", tmp_path)
    assert result.returncode == 0


def test_exits_zero_on_empty_stdin(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT)], input="", capture_output=True, text=True, env=env
    )
    assert result.returncode == 0


def test_exits_zero_on_malformed_json(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT)], input="not valid json{{{", capture_output=True, text=True, env=env
    )
    assert result.returncode == 0


def test_writes_log_entry_on_block(tmp_path):
    _run_hook("rm -rf /tmp/some-dir", tmp_path)

    log_file = tmp_path / ".claude-blocked-commands.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "rm -rf /tmp/some-dir" in content


def test_no_log_entry_on_safe_command(tmp_path):
    _run_hook("ls -la", tmp_path)

    log_file = tmp_path / ".claude-blocked-commands.log"
    assert not log_file.exists()


def test_block_still_happens_when_osascript_fails(tmp_path):
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_osascript = fake_bin / "osascript"
    fake_osascript.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fake_osascript.chmod(0o755)

    result = _run_hook("rm -rf /tmp/some-dir", tmp_path, extra_path=str(fake_bin))

    assert result.returncode == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_block_dangerous_bash.py -v`
Expected: FAIL — `.claude/hooks/block-dangerous-bash.sh` doesn't exist yet, every `subprocess.run(["bash", str(SCRIPT)], ...)` raises `FileNotFoundError`.

- [ ] **Step 3: Write the script**

```bash
mkdir -p ~/workspaces/multi-agent/.claude/hooks
```

`.claude/hooks/block-dangerous-bash.sh`:
```bash
#!/usr/bin/env bash
# PreToolUse hook for Bash tool calls.
# Reads the pending command from stdin JSON and blocks it (exit 2) if it
# matches a known-dangerous pattern. Exit 0 lets the tool call proceed.
#
# Unlike the Stop hook (check-team-progress.sh), PreToolUse uses an
# exit-code protocol, not JSON: exit 2 blocks the tool call and Claude
# Code shows our stderr to the model as the block reason; exit 0 allows
# it. This exact mechanism was already live-verified in a separate
# learning project (claude-code-understanding, commit d93fb14) before
# being adapted here — the patterns below are that script's, unchanged.

set -euo pipefail

PAYLOAD="$(cat)"

COMMAND="$(printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
cmd = data.get("tool_input", {}).get("command", "")
print(cmd)
')"

if [ -z "$COMMAND" ]; then
    exit 0
fi

LOG_FILE="$HOME/.claude-blocked-commands.log"

block() {
    local reason="$1"
    local pane="${TMUX_PANE:-no-pane}"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    echo "BLOCKED by block-dangerous-bash.sh: $reason" >&2
    echo "Command was: $COMMAND" >&2

    printf '%s | %s | %s | %s\n' "$timestamp" "$pane" "$reason" "$COMMAND" >> "$LOG_FILE" 2>/dev/null || true

    osascript -e "display notification \"pane ${pane}: ${COMMAND}\" with title \"위험 명령 차단\" sound name \"Basso\"" >/dev/null 2>&1 || true

    exit 2
}

# --- Dangerous pattern checks -------------------------------------------

# rm -rf (any target) -- catches rm -rf, rm -fr, rm -r -f, sudo rm -rf, etc.
if printf '%s' "$COMMAND" | grep -Eq '\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\b|\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\b'; then
    block "destructive 'rm -rf'-style recursive force delete is not allowed."
fi

# git push --force / -f (including --force-with-lease variants we still want to flag)
if printf '%s' "$COMMAND" | grep -Eq '\bgit\s+push\b.*(--force\b|--force-with-lease\b|-f\b)'; then
    block "force-pushing to a remote ('git push --force'/'-f') is not allowed."
fi

# git push origin main / git push origin master (main 브랜치 직접 push 차단)
if printf '%s' "$COMMAND" | grep -Eq '\bgit\s+push\s+\S+\s+(main|master)\b'; then
    block "direct push to main/master branch is not allowed. Use a feature branch and PR."
fi

# Reading .env files (cat/less/more/head/tail/vi/nano/cp/mv exposing secrets)
if printf '%s' "$COMMAND" | grep -Eq '(^|[/[:space:]])\.env([.[:space:]]|$)|(^|[/[:space:]])\.env\.[A-Za-z0-9_.-]+'; then
    block "reading or exposing .env files is not allowed (may contain secrets)."
fi

exit 0
```

```bash
chmod +x ~/workspaces/multi-agent/.claude/hooks/block-dangerous-bash.sh
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_block_dangerous_bash.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add .claude/hooks/block-dangerous-bash.sh test_block_dangerous_bash.py
git commit -m "feat: add block-dangerous-bash.sh PreToolUse hook + tests"
```

---

### Task 2: Wire into settings.json + manual verification

**Files:**
- Modify: `.claude/settings.json`

**Interfaces:**
- Consumes: `.claude/hooks/block-dangerous-bash.sh` from Task 1 (invoked by path).
- Produces: a working `PreToolUse` hook active for every Bash tool call in this project directory, coexisting with the existing `Stop` hook in the same file.

- [ ] **Step 1: Read the current file and add PreToolUse alongside Stop**

Current `.claude/settings.json` (from Track B, do not remove or reorder this):
```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/check-team-progress.sh"
          }
        ]
      }
    ]
  }
}
```

New `.claude/settings.json` (add `PreToolUse` as a sibling key to `Stop`, inside the same `hooks` object):
```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/check-team-progress.sh"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/block-dangerous-bash.sh"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Validate the JSON parses and both hook keys are present**

Run: `cd ~/workspaces/multi-agent && python3 -c "import json; d = json.load(open('.claude/settings.json')); assert 'Stop' in d['hooks']; assert 'PreToolUse' in d['hooks']; print('valid json, both hooks present')"`
Expected: `valid json, both hooks present`

- [ ] **Step 3: Commit**

```bash
cd ~/workspaces/multi-agent
git add .claude/settings.json
git commit -m "feat: wire block-dangerous-bash.sh into the PreToolUse hook"
```

- [ ] **Step 4: Manual live verification**

This step cannot be automated — it requires an interactive Claude Code session observing its own PreToolUse-hook behavior live. Unlike Track B's Stop hook (which required extensive live debugging because the mechanism itself was unverified), this exit-2-blocking mechanism was already proven in the precedent project — this pass is to confirm the *wiring* in this specific repo, not to re-derive the mechanism.

1. In a terminal: `cd ~/workspaces/multi-agent && claude`
2. Ask it to run a blocked command directly: "bash로 `rm -rf /tmp/some-test-dir-that-does-not-exist` 실행해줘"
3. Confirm Claude's tool call is blocked — it should report being unable to run the command and mention the reason (not silently retry, not succeed)
4. Check the log: `cat ~/.claude-blocked-commands.log` — expect one line with today's timestamp, a pane id, the reason, and the command
5. Confirm a desktop notification appeared titled "위험 명령 차단" (if notifications are enabled for the terminal app in System Settings — note this in the report if it didn't appear, since notification permissions are a one-time system-level grant outside this hook's control)
6. Ask it to run a safe command: "bash로 `ls` 실행해줘" — confirm it runs normally, no block, no new log line
7. Confirm the Track B Stop hook still works alongside this: ask it to edit `docs/architecture.md` and confirm (via `git -C ~/workspaces/multi-agent-wiki log --oneline | wc -l` before/after) the Stop hook still fires as it did before this change — the two hooks must not interfere with each other
8. Record the outcome (pass/fail per step) and report back — do not declare this task done until live behavior matches expectations for both hooks coexisting

If step 3 or 7 doesn't match expectations, stop and report — do not proceed to declare this task done.
