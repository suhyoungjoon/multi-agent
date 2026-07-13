import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / ".claude" / "hooks" / "check-team-progress.sh"


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "docs").mkdir()
    (repo / "docs" / "architecture.md").write_text("initial\n", encoding="utf-8")
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)
    return repo


def _run_script(repo: Path, pane: str | None = None) -> subprocess.CompletedProcess:
    """`pane` simulates $TMUX_PANE — pass a distinct value per simulated tmux
    pane so state tracking is independent between them, or None to simulate
    running outside tmux (no TMUX_PANE set)."""
    env = os.environ.copy()
    if pane is not None:
        env["TMUX_PANE"] = pane
    else:
        env.pop("TMUX_PANE", None)
    return subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True, env=env)


def test_emits_block_decision_when_docs_file_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "산출물이 바뀌었습니다" in payload["reason"]


def test_emits_block_decision_when_memory_store_file_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "memory_store").mkdir()
    (repo / "memory_store" / "store.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add memory_store"], cwd=repo, check=True)
    (repo / "memory_store" / "store.py").write_text("x = 2\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"


def test_emits_block_decision_when_todo_py_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "todo.py").write_text("# v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add todo.py"], cwd=repo, check=True)
    (repo / "todo.py").write_text("# v2\n", encoding="utf-8")

    result = _run_script(repo)

    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"


def test_silent_when_only_unrelated_file_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("updated readme\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_silent_when_nothing_changed(tmp_path):
    repo = _init_repo(tmp_path)

    result = _run_script(repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_exits_zero_when_not_a_git_repo(tmp_path):
    not_repo = tmp_path / "not_a_repo"
    not_repo.mkdir()

    result = _run_script(not_repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_emits_block_decision_when_untracked_file_created_under_docs(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "newfile.md").write_text("brand new file\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"


def test_reason_mentions_all_six_team_members(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated\n", encoding="utf-8")

    result = _run_script(repo)

    payload = json.loads(result.stdout)
    for name in ["쭌", "민준", "지훈", "수아", "서연", "태양"]:
        assert name in payload["reason"]


def test_silent_on_second_call_when_no_new_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    first = _run_script(repo)
    second = _run_script(repo)

    assert json.loads(first.stdout)["decision"] == "block"
    assert second.stdout == ""


def test_emits_again_when_additional_relevant_change_occurs(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    first = _run_script(repo)
    assert json.loads(first.stdout)["decision"] == "block"

    (repo / "docs" / "api-spec.md").write_text("new file\n", encoding="utf-8")
    second = _run_script(repo)

    assert json.loads(second.stdout)["decision"] == "block"


def test_fires_again_after_change_is_committed_then_a_new_change_appears(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    first = _run_script(repo)
    assert json.loads(first.stdout)["decision"] == "block"

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "commit the change"], cwd=repo, check=True)
    silent_after_commit = _run_script(repo)
    assert silent_after_commit.stdout == ""

    (repo / "docs" / "architecture.md").write_text("updated again\n", encoding="utf-8")
    third = _run_script(repo)
    assert json.loads(third.stdout)["decision"] == "block"


def test_reason_names_the_specific_changed_path(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    result = _run_script(repo)

    payload = json.loads(result.stdout)
    assert "docs/architecture.md" in payload["reason"]


def test_second_persona_still_notified_when_first_persona_already_reported(tmp_path):
    """Real concurrent-pane repro: 지훈 saves docs/research.md (his turn is still in
    progress, no Stop yet) BEFORE 민준's Stop event fires — so when 민준's hook runs,
    `git status` already shows both files dirty. 민준's Stop (pane A) fires and,
    with the old shared-state design, would mark 지훈's still-unreported file as
    "seen" too. 지훈's own Stop (pane B) must still fire for his own file — pane-scoped
    state (keyed by $TMUX_PANE) is what makes this possible: pane B never reads
    anything pane A wrote."""
    repo = _init_repo(tmp_path)

    # 지훈's edit lands on disk first, but his turn hasn't Stopped yet.
    (repo / "docs" / "research.md").write_text("지훈's change\n", encoding="utf-8")
    # 민준 edits his own file and Stops — both files are dirty at this point.
    (repo / "docs" / "architecture.md").write_text("민준's change\n", encoding="utf-8")

    minjun_run = _run_script(repo, pane="%1")
    assert json.loads(minjun_run.stdout)["decision"] == "block"

    # 지훈's Stop fires next, on pane B — nothing about research.md has changed
    # further, but it must still be reported since pane B has never reported it.
    jihoon_run = _run_script(repo, pane="%2")

    assert jihoon_run.stdout != "", "지훈's own unreported change was silently swallowed"
    payload = json.loads(jihoon_run.stdout)
    assert payload["decision"] == "block"
    assert "docs/research.md" in payload["reason"]


def test_panes_without_tmux_pane_set_fall_back_to_shared_state(tmp_path):
    """Outside tmux (no $TMUX_PANE), there's only ever one consumer, so falling
    back to one shared state file is correct and matches pre-pane-scoping
    behavior — verifies the fallback doesn't silently disable state tracking."""
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated\n", encoding="utf-8")

    first = _run_script(repo, pane=None)
    second = _run_script(repo, pane=None)

    assert json.loads(first.stdout)["decision"] == "block"
    assert second.stdout == ""


def test_reason_joins_multiple_changed_paths_with_comma_space(tmp_path):
    """Regression test for a delimiter bug: BSD paste's -d takes a *rotating*
    delimiter list, not a literal separator, so `paste -sd ', ' -` silently
    produces comma-with-no-space or inconsistent joins on macOS. Assert the
    actual joined format instead of just substring-checking each path."""
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("change one\n", encoding="utf-8")
    (repo / "docs" / "research.md").write_text("change two\n", encoding="utf-8")
    (repo / "docs" / "review.md").write_text("change three\n", encoding="utf-8")

    result = _run_script(repo)

    payload = json.loads(result.stdout)
    assert "docs/architecture.md, docs/research.md, docs/review.md" in payload["reason"]


def test_no_false_reretrigger_when_unrelated_commit_happens_elsewhere(tmp_path):
    """A commit that only touches an already-reported path must not cause a
    still-pending, unrelated, already-reported path to be re-announced."""
    repo = _init_repo(tmp_path)

    (repo / "docs" / "architecture.md").write_text("first change\n", encoding="utf-8")
    (repo / "docs" / "research.md").write_text("second change\n", encoding="utf-8")
    first = _run_script(repo)
    assert json.loads(first.stdout)["decision"] == "block"

    # Commit only architecture.md; research.md remains uncommitted and unchanged.
    subprocess.run(["git", "add", "docs/architecture.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "commit architecture only"], cwd=repo, check=True)

    second = _run_script(repo)

    assert second.stdout == ""


def test_emits_block_decision_for_new_file_in_wholly_untracked_subdirectory(tmp_path):
    """Final whole-branch review found a real gap: git status --porcelain
    (without -uall) collapses a wholly-untracked directory to a single
    directory entry (e.g. "?? docs/research/"), not the individual file.
    git hash-object then fails on that directory path and the change is
    silently dropped. This matters for real usage: docs/research/ (지훈),
    docs/design/ (수아), and docs/review/ (태양) are all untracked in the
    actual multi-agent repo, so every file they create would be invisible
    to the hook without this fix."""
    repo = _init_repo(tmp_path)
    (repo / "docs" / "research").mkdir()
    (repo / "docs" / "research" / "topic.md").write_text("research notes\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "docs/research/topic.md" in payload["reason"]


def test_emits_block_decision_for_korean_filename(tmp_path):
    """Final whole-branch review found a second real gap: with git's default
    core.quotepath=true, a non-ASCII filename is octal-escaped and
    double-quoted in `git status --porcelain` output (e.g.
    '"docs/research/\\354\\241\\260\\354\\202\\254.md"'), which breaks both
    the path regex match and git hash-object. Highly relevant for this
    all-Korean-filename project."""
    repo = _init_repo(tmp_path)
    (repo / "docs" / "research").mkdir()
    (repo / "docs" / "research" / "조사.md").write_text("조사 내용\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "docs/research/조사.md" in payload["reason"]
