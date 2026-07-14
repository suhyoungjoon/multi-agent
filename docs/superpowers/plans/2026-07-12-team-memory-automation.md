# 팀 기억 자동화 (Track B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> ⚠️ **이 계획 문서는 실제 구현과 다릅니다 (2026-07-13 기준).** 라이브 tmux 검증 중 이 문서에 적힌 메커니즘(`TEAM_PROGRESS_CHANGED:` plain stdout, `git diff --name-only HEAD` 게이팅)이 Stop 이벤트에서 실제로 동작하지 않는 것으로 판명되어 완전히 재설계됐습니다. **정확한 최신 동작은 스펙 문서(`docs/superpowers/specs/2026-07-12-team-memory-automation-design.md`)를 참고하세요** — 이 계획 파일은 초기 태스크 분해 기록으로만 남겨둡니다.

**Goal:** Add a `Stop` hook to `multi-agent/.claude/settings.json` that detects (via `git diff`) whether a team member's output changed this response, and if so, instructs Claude to record a summary in that member's `wiki/team/<name>.md` and auto-commit it in the vault repo.

**Architecture:** A standalone, unit-testable bash script (`.claude/hooks/check-team-progress.sh`) does the git-diff gating and emits the instruction text on stdout when relevant paths changed. `.claude/settings.json` wires this script to the `Stop` event via `type: command`. This is a packaging refinement over the spec (which showed the logic as one inline JSON string) — same behavior, but the gating logic becomes independently testable instead of buried in a JSON string.

**Tech Stack:** bash, git, pytest (for testing the script via `subprocess`, matching this repo's existing test convention — see `studio/tests/`, `test_memory_store.py`).

## Global Constraints

- Read the spec first: `docs/superpowers/specs/2026-07-12-team-memory-automation-design.md` — every task below implements a section of it.
- Detected paths (must match exactly, per spec's "감지 대상 경로"): `docs/`, `memory_store/`, `cloud-builder/`, `todo.py`, `test_` (prefix match on any of these).
- Script must never exit non-zero and must never print anything when nothing relevant changed (a Stop hook that errors or prints noise on every turn is worse than no hook).
- Do not modify `.claude/settings.local.json` — hooks go in the new `.claude/settings.json` only (local file stays permissions-only, per spec).
- Do not modify `~/workspaces/multi-agent-wiki` in this plan — the hook *instructs* Claude to modify it at runtime; this plan does not touch that repo.
- Run tests with: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_check_team_progress.py -v` (reuses the project's existing `.venv` — see `studio/README.md` if it needs recreating).

---

### Task 1: `check-team-progress.sh` — gating script + tests

**Files:**
- Create: `.claude/hooks/check-team-progress.sh`
- Test: `test_check_team_progress.py` (repo root, alongside `test_memory_store.py` / `test_todo.py` — this repo's existing flat test-file convention)

**Interfaces:**
- Produces: an executable script at `.claude/hooks/check-team-progress.sh` that takes no arguments, reads the current working directory's git state, and either prints one line starting with `TEAM_PROGRESS_CHANGED:` (relevant paths changed) or prints nothing (no relevant change / not a git repo). Always exits 0.

- [ ] **Step 1: Write the failing tests**

`test_check_team_progress.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_check_team_progress.py -v`
Expected: FAIL — `.claude/hooks/check-team-progress.sh` doesn't exist yet, so every `subprocess.run(["bash", str(SCRIPT)], ...)` call raises `FileNotFoundError` (bash reports "No such file or directory"), surfacing as errors rather than assertion failures.

- [ ] **Step 3: Write the script**

```bash
mkdir -p ~/workspaces/multi-agent/.claude/hooks
```

`.claude/hooks/check-team-progress.sh`:
```bash
#!/bin/bash
# Stop hook: detect whether team-output paths changed this response.
# If so, print an instruction telling Claude to record it in the vault.
# Must never fail the hook chain — always exits 0, silent when there's
# nothing to report.
set -uo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

if git diff --name-only HEAD 2>/dev/null | grep -qE '^(docs/|memory_store/|cloud-builder/|todo\.py|test_)'; then
  echo 'TEAM_PROGRESS_CHANGED: 이번 세션에서 산출물이 바뀌었습니다. 지금까지의 대화 맥락에서 네가 어느 팀원(쭌/민준/지훈/수아/서연/태양)인지 판단한 뒤, ~/workspaces/multi-agent-wiki 디렉토리로 가서 bash scripts/wiki-lock.sh acquire wiki/team/<이름>.md 로 락을 잡고, wiki/team/<이름>.md 파일의 "## 최근 작업" 섹션에 이번 세션에서 한 일을 3~5문장으로 요약해 추가(append, 기존 내용 유지)한 뒤, git add 및 git commit을 실행하고, bash scripts/wiki-lock.sh release wiki/team/<이름>.md 로 락을 해제하라.'
fi

exit 0
```

```bash
chmod +x ~/workspaces/multi-agent/.claude/hooks/check-team-progress.sh
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_check_team_progress.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/multi-agent
git add .claude/hooks/check-team-progress.sh test_check_team_progress.py
git commit -m "feat: add check-team-progress.sh gating script for Stop hook"
```

---

### Task 2: Wire the hook into settings.json + manual end-to-end verification

**Files:**
- Create: `.claude/settings.json`

**Interfaces:**
- Consumes: `.claude/hooks/check-team-progress.sh` from Task 1 (invoked by path, not imported).
- Produces: a working `Stop` hook active for every pane opened in this project directory once the file exists (no other task depends on this one — it's the integration point).

- [ ] **Step 1: Write settings.json**

`.claude/settings.json`:
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

- [ ] **Step 2: Validate the JSON parses**

Run: `cd ~/workspaces/multi-agent && python3 -c "import json; json.load(open('.claude/settings.json')); print('valid json')"`
Expected: `valid json`

- [ ] **Step 3: Commit**

```bash
cd ~/workspaces/multi-agent
git add .claude/settings.json
git commit -m "feat: wire check-team-progress.sh into the Stop hook"
```

- [ ] **Step 4: Manual end-to-end verification**

This step cannot be automated — it requires an interactive Claude Code session observing its own Stop-hook behavior live. Run through it once after Task 2 Step 3 is committed:

1. In a terminal (not this session — a fresh one, since hooks are read at session start): `cd ~/workspaces/multi-agent && claude`
2. Note the current vault commit count for comparison: `git -C ~/workspaces/multi-agent-wiki log --oneline | wc -l`
3. Ask the new session: "docs/architecture.md 맨 끝에 '- 테스트 라인' 한 줄만 추가해줘" (a real, tracked-file edit under a detected path)
4. After it finishes that turn, check whether the vault gained a new commit: `git -C ~/workspaces/multi-agent-wiki log --oneline | wc -l` — expect count increased by 1, and `git -C ~/workspaces/multi-agent-wiki log -1 --stat` should show a `wiki/team/<some-name>.md` change
5. Confirm the new commit's file has a new line under `## 최근 작업` (not a full overwrite of the file — the rest of the file should be untouched)
6. In the same session, ask something with no file impact: "2+2는 얼마야?" — after it answers, re-check `git -C ~/workspaces/multi-agent-wiki log --oneline | wc -l` again and confirm the count did **not** increase (silent gating on unrelated turns)
7. Revert the test edit so `docs/architecture.md` doesn't carry a stray line: `cd ~/workspaces/multi-agent && git checkout -- docs/architecture.md` (only if it was already tracked/committed before this test — if step 3 was the file's first-ever edit, use `git diff` to confirm before reverting anything)
8. Record the outcome (pass/fail, which persona name it picked, any misfire) as a short note back to the user — do not silently assume success

If step 4 or 6 doesn't match expectations, stop and report — do not proceed to declare this task done until the live behavior matches the spec's "검증 방법" section.

**Note on spec verification item 4 (concurrent-pane wiki-lock simulation):** not repeated here. `scripts/wiki-lock.sh`'s locking correctness under concurrent writers already has dedicated coverage in the vault repo itself (`test_wiki_lock.sh`, `test_concurrent_write.sh` — see `~/workspaces/multi-agent-wiki`'s own `make test`). This plan reuses that script rather than reimplementing locking, so re-verifying its concurrency behavior here would duplicate tests that already exist upstream. If a real concurrent-pane collision is ever observed in daily use, that's a signal to re-open this — not something to script preemptively.

---

## Explicitly deferred (per spec's 제외 범위)

- SessionStart hook (loading prior context back in) — separate future spec.
- Deterministic pane→persona mapping (e.g. `$TMUX_PANE`-based) — only revisit if LLM self-identification proves unreliable in practice.
- Any changes to the claude-obsidian plugin's own hooks — out of scope, untouched.
