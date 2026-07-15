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


# --- Regression tests for final-review findings I1/I2 -----------------------


def test_blocks_rm_capital_rf(tmp_path):
    """I1: 'rm -Rf' (capital R) slipped through the original case-sensitive regex."""
    result = _run_hook("rm -Rf /tmp/some-dir", tmp_path)
    assert result.returncode == 2


def test_blocks_rm_long_flags(tmp_path):
    """I1: '--recursive --force' (long-form flags) slipped through the original regex."""
    result = _run_hook("rm --recursive --force /tmp/some-dir", tmp_path)
    assert result.returncode == 2


def test_blocks_rm_mixed_short_and_long_flags(tmp_path):
    """I1: mixed short recursive + long force slipped through the original regex."""
    result = _run_hook("rm -r --force /tmp/some-dir", tmp_path)
    assert result.returncode == 2


def test_allows_rm_force_only_no_recursion(tmp_path):
    """Force-only single-file delete (no recursion) must still be allowed —
    the fix for I1 must not overreach into blocking this."""
    result = _run_hook("rm -f /tmp/some-file.txt", tmp_path)
    assert result.returncode == 0


def test_allows_rm_plain_no_flags(tmp_path):
    result = _run_hook("rm /tmp/some-file.txt", tmp_path)
    assert result.returncode == 0


def test_notification_passes_command_as_data_not_applescript_source(tmp_path):
    """I2: $COMMAND was interpolated directly into the AppleScript -e source
    string, so a command containing a literal '"' could break out of the
    string and inject arbitrary AppleScript (verified live: a crafted
    command executed `do shell script "..."` via the notification call).
    The fix must pass the command as a plain data argument to osascript
    (e.g. via `on run argv`), never concatenated into -e script source."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_osascript = fake_bin / "osascript"
    capture_file = tmp_path / "osascript-calls.log"
    fake_osascript.write_text(
        f'#!/bin/sh\nfor a in "$@"; do printf \'%s\\n---ARG---\\n\' "$a"; done >> "{capture_file}"\nexit 0\n',
        encoding="utf-8",
    )
    fake_osascript.chmod(0o755)

    malicious = 'rm -rf /tmp/x" & (do shell script "touch PWNED-marker") & "'
    result = _run_hook(malicious, tmp_path, extra_path=str(fake_bin))

    assert result.returncode == 2
    assert capture_file.exists()
    args = [a for a in capture_file.read_text(encoding="utf-8").split("---ARG---\n") if a]

    script_args = [args[i + 1] for i, a in enumerate(args[:-1]) if a == "-e"]
    for script in script_args:
        assert "do shell script" not in script
        assert malicious not in script

    # The malicious text must still show up somewhere (as a plain data
    # argument), proving it wasn't silently dropped -- just safely isolated
    # from the AppleScript source.
    assert any(malicious in a for a in args)
