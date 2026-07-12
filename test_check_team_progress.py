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


def test_emits_notice_when_docs_file_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "architecture.md").write_text("updated content\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    assert "TEAM_PROGRESS_CHANGED" in result.stdout


def test_emits_notice_when_memory_store_file_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "memory_store").mkdir()
    (repo / "memory_store" / "store.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add memory_store"], cwd=repo, check=True)
    (repo / "memory_store" / "store.py").write_text("x = 2\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    assert "TEAM_PROGRESS_CHANGED" in result.stdout


def test_emits_notice_when_todo_py_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "todo.py").write_text("# v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add todo.py"], cwd=repo, check=True)
    (repo / "todo.py").write_text("# v2\n", encoding="utf-8")

    result = _run_script(repo)

    assert "TEAM_PROGRESS_CHANGED" in result.stdout


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


def test_emits_notice_when_untracked_file_created_under_docs(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "newfile.md").write_text("brand new file\n", encoding="utf-8")

    result = _run_script(repo)

    assert result.returncode == 0
    assert "TEAM_PROGRESS_CHANGED" in result.stdout
