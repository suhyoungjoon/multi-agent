import json
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


def _run_script(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True)


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
    """Simulates two tmux panes sharing one working tree: 민준 edits docs/architecture.md
    and the hook fires (reporting it), then — before either change is committed —
    지훈 edits a different file under docs/. 지훈's Stop event must still fire for
    their own file, not go silent just because 민준's file was already reported."""
    repo = _init_repo(tmp_path)

    (repo / "docs" / "architecture.md").write_text("민준's change\n", encoding="utf-8")
    minjun_run = _run_script(repo)
    assert json.loads(minjun_run.stdout)["decision"] == "block"

    (repo / "docs" / "research.md").write_text("지훈's change\n", encoding="utf-8")
    jihoon_run = _run_script(repo)

    assert jihoon_run.stdout != ""
    payload = json.loads(jihoon_run.stdout)
    assert payload["decision"] == "block"
    assert "docs/research.md" in payload["reason"]
    # Should not re-announce 민준's already-reported file as if it were new.
    assert "docs/architecture.md" not in payload["reason"]


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
