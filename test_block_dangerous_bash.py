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
