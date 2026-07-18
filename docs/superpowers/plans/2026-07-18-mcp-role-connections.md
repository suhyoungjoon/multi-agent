# MCP 역할별 연결 (Track C 후반) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each of 4 team personas (민준, 수아, 서연, 태양) their own MCP server set via per-role `.mcp/*.json` config files, wired into `setup-team-v2.sh`'s pane-launch command through `--mcp-config`/`--strict-mcp-config`, with `team.yaml` as the source of which persona gets which config file.

**Architecture:** `.mcp/*.json` files hold standard Claude Code `--mcp-config` JSON. `team.yaml` gains a `mcp_config` field per member (path to that file, or `null`). `setup-team-v2.sh` reads this field the same way it already reads `MEMBER_NAMES`/`MEMBER_MODELS` (bash-3.2-compatible `while read` loop over an inline `python3 -c` snippet) and conditionally appends `--mcp-config <file> --strict-mcp-config` to that pane's launch command. GitHub MCP's token is never written in plaintext — `.mcp/서연.json`/`.mcp/태양.json` reference `${GITHUB_PAT}`, sourced from the repo's existing `.env` (already gitignored) before panes launch.

**Tech Stack:** YAML, JSON, Python (PyYAML, already a dependency), bash 3.2-compatible.

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-18-mcp-role-connections-design.md` — every task below implements a section of it.
- This machine's only bash is `/bin/bash` 3.2.57 (no `readarray`/`mapfile`, no `declare -A`-with-string-arithmetic reliability — confirmed during Track A). Any new array-population code in `setup-team-v2.sh` MUST use the `while IFS= read -r line; do VAR+=("$line"); done < <(...)` pattern, never `readarray`.
- Never write a real token in plaintext into any file tracked by git. `.mcp/서연.json` and `.mcp/태양.json` use `${GITHUB_PAT}` (matches the variable name already used in the repo's existing `.env` — confirmed via `grep -o '^[A-Z_]*=' .env` returning `GITHUB_PAT=`). Do not introduce a differently-named variable.
- Every consumer must degrade gracefully: missing `.env`, missing `team.yaml`, missing `mcp_config` field, or a member with `mcp_config: null` must all result in that pane launching exactly as it did before this feature existed (no `--mcp-config`/`--strict-mcp-config` flags), never a launch failure.
- 쭌 and 지훈 get `mcp_config: null` — do not give them MCP servers (see spec's 아키텍처 section for why).
- Do not touch `~/.claude.json`'s existing global GitHub MCP entry — out of scope per spec.
- **Do not run `claude -p ...` with `--mcp-config` from inside `/Users/syj/workspaces/multi-agent`** — this repo's `.claude/settings.json` has a `Stop` hook (`check-team-progress.sh`) that fires on any Claude Code session exit in this directory, including one-shot `-p` smoke tests, and will prompt persona/wiki-commit behavior unrelated to this task. Run any live `--mcp-config` smoke test from a directory with no `.claude/settings.json` (e.g. a fresh `/tmp` subdirectory).
- Do not run the full `setup-team-v2.sh` (would launch a real interactive 6-pane tmux session) — verification is via `bash -n`, isolated dry-runs of the new array-population blocks, and the one live smoke test outside this repo, matching Track A's established verification approach.

---

### Task 1: `.mcp/` config files

**Files:**
- Create: `.mcp/민준.json`
- Create: `.mcp/수아.json`
- Create: `.mcp/서연.json`
- Create: `.mcp/태양.json`
- Test: `test_mcp_configs.py` (repo root, alongside `test_block_dangerous_bash.py` and `test_check_team_progress.py`)

**Interfaces:**
- Produces: 4 valid JSON files, each parseable by Claude Code's `--mcp-config` loader (top-level `mcpServers` object). `.mcp/서연.json` and `.mcp/태양.json` reference `${GITHUB_PAT}` — never a literal token.

- [ ] **Step 1: Write the failing test**

`test_mcp_configs.py`:
```python
import json
import re
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent / ".mcp"

ALL_CONFIGS = ["민준.json", "수아.json", "서연.json", "태양.json"]
TOKEN_LEAK_PATTERN = re.compile(r"ghp_[A-Za-z0-9]{20,}")


def test_all_configs_exist():
    for name in ALL_CONFIGS:
        assert (MCP_DIR / name).is_file(), f"{name} missing"


def test_all_configs_are_valid_json_with_mcpServers():
    for name in ALL_CONFIGS:
        data = json.loads((MCP_DIR / name).read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert isinstance(data.get("mcpServers"), dict)
        assert len(data["mcpServers"]) >= 1


def test_minjun_has_context7_only():
    data = json.loads((MCP_DIR / "민준.json").read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"context7"}


def test_sua_has_browser_only():
    data = json.loads((MCP_DIR / "수아.json").read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"browser"}


def test_seoyeon_has_github_only():
    data = json.loads((MCP_DIR / "서연.json").read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"github"}


def test_taeyang_has_browser_and_github():
    data = json.loads((MCP_DIR / "태양.json").read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"browser", "github"}


def test_github_configs_reference_env_var_not_literal_token():
    for name in ["서연.json", "태양.json"]:
        text = (MCP_DIR / name).read_text(encoding="utf-8")
        assert "${GITHUB_PAT}" in text
        assert not TOKEN_LEAK_PATTERN.search(text), f"{name} contains a literal-looking GitHub token"


def test_no_config_contains_a_literal_github_token():
    for name in ALL_CONFIGS:
        text = (MCP_DIR / name).read_text(encoding="utf-8")
        assert not TOKEN_LEAK_PATTERN.search(text), f"{name} contains a literal-looking GitHub token"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/syj/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_mcp_configs.py -v`
Expected: FAIL — `.mcp/` directory and all 4 files don't exist yet (`test_all_configs_exist` fails first).

- [ ] **Step 3: Create the 4 config files**

`.mcp/민준.json`:
```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

`.mcp/수아.json`:
```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

`.mcp/서연.json`:
```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    }
  }
}
```

`.mcp/태양.json`:
```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}"
      }
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/syj/workspaces/multi-agent && ./.venv/bin/python3 -m pytest test_mcp_configs.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/syj/workspaces/multi-agent
git add .mcp/ test_mcp_configs.py
git commit -m "feat: add per-role MCP config files (민준/수아/서연/태양)"
```

---

### Task 2: `team.yaml` — add `mcp_config` field

**Files:**
- Modify: `team.yaml`
- Test: `studio/tests/test_team_config.py` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: every member dict returned by `team_config.load_team()` now may contain an `mcp_config` key (string path, or `null`/absent for 쭌/지훈 and for the script-parsing/hardcoded fallback tiers, which never had this field and don't need it — those tiers only run when `team.yaml` itself is unavailable, at which point MCP role-assignment is moot).

- [ ] **Step 1: Write the failing test**

Append to `studio/tests/test_team_config.py`:
```python
def test_default_team_yaml_has_mcp_config_for_four_members():
    team = team_config.load_team()
    by_name = {m["name"]: m for m in team}

    assert by_name["민준"]["mcp_config"] == ".mcp/민준.json"
    assert by_name["수아"]["mcp_config"] == ".mcp/수아.json"
    assert by_name["서연"]["mcp_config"] == ".mcp/서연.json"
    assert by_name["태양"]["mcp_config"] == ".mcp/태양.json"
    assert by_name["쭌"].get("mcp_config") is None
    assert by_name["지훈"].get("mcp_config") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/syj/workspaces/multi-agent && ./.venv/bin/python3 -m pytest studio/tests/test_team_config.py::test_default_team_yaml_has_mcp_config_for_four_members -v`
Expected: FAIL — `mcp_config` key doesn't exist on any member yet (`KeyError` via `by_name["민준"]["mcp_config"]`).

- [ ] **Step 3: Add `mcp_config` field to each member in `team.yaml`**

For each of the 6 members in `team.yaml`, add an `mcp_config` line as the last field. Use `Edit`, not a full rewrite — insert directly after each member's existing `owns_files: []` line:

쭌's block gets:
```yaml
    owns_files: []
    mcp_config: null
```

민준's block gets:
```yaml
    owns_files: []
    mcp_config: .mcp/민준.json
```

지훈's block gets:
```yaml
    owns_files: []
    mcp_config: null
```

수아's block gets:
```yaml
    owns_files: []
    mcp_config: .mcp/수아.json
```

서연's block gets:
```yaml
    owns_files: []
    mcp_config: .mcp/서연.json
```

태양's block gets:
```yaml
    owns_files: []
    mcp_config: .mcp/태양.json
```

No other lines in `team.yaml` change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/syj/workspaces/multi-agent && ./.venv/bin/python3 -m pytest studio/tests/test_team_config.py -v`
Expected: PASS (all tests, including the new one — this also re-confirms none of the existing 10 team_config tests broke)

- [ ] **Step 5: Run the full studio suite to confirm no regressions**

Run: `cd /Users/syj/workspaces/multi-agent && ./.venv/bin/python3 -m pytest studio/tests/ -v`
Expected: PASS (all tests — `studio/roles.py`, `studio/main.py`, `studio/watchdog_loop.py` only read `pane`/`role`/`name`/`model` fields and ignore unknown keys, so adding `mcp_config` must not break them)

- [ ] **Step 6: Commit**

```bash
cd /Users/syj/workspaces/multi-agent
git add team.yaml studio/tests/test_team_config.py
git commit -m "feat: add mcp_config field to team.yaml for 4 personas"
```

---

### Task 3: `setup-team-v2.sh` — wire `--mcp-config`/`--strict-mcp-config` + `.env` loading

**Files:**
- Modify: `setup-team-v2.sh`

**Interfaces:**
- Consumes: `team.yaml`'s `mcp_config` field (Task 2), `.mcp/*.json` files (Task 1), repo-root `.env` (pre-existing, holds `GITHUB_PAT=...`).
- Produces: pane-launch commands that include `--mcp-config <file> --strict-mcp-config` when that persona's `mcp_config` is non-null, and omit both flags otherwise (identical to current behavior).

- [ ] **Step 1: Current state (for reference — no action yet)**

`setup-team-v2.sh` currently has this exact block at lines 32-56 (the `MEMBER_MODELS` population, added in Track A):

```bash
MEMBER_MODELS=()
while IFS= read -r line; do
    MEMBER_MODELS+=("$line")
done < <(python3 -c "
import yaml
try:
    with open('team.yaml') as f:
        data = yaml.safe_load(f)
    for m in sorted(data['team'], key=lambda x: x['pane']):
        print(m['model'])
except Exception:
    pass
" 2>/dev/null)

if [ "${#MEMBER_NAMES[@]}" -eq 0 ]; then
    MEMBER_NAMES=("쭌" "민준 아키텍트" "지훈 리서쳐" "수아 UI/UX디자이너" "서연 개발자" "태양 QA·리뷰어")
    MEMBER_MODELS=(
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
        "claude-sonnet-4-6"
    )
fi
```

And the pane-launch line at line 141-142 (inside the `for i in 0 1 2 3 4 5; do ... done` loop starting at line 137):

```bash
    tmux send-keys -t "$pane" \
        "cd '$WORKDIR' && unset CLAUDECODE && $CLAUDE_BIN --model ${MEMBER_MODELS[$i]} --dangerously-skip-permissions" Enter
```

- [ ] **Step 2: Add `.env` loading and `mcp_config` array population**

Using `Edit`, insert this new block immediately after the `if [ "${#MEMBER_NAMES[@]}" -eq 0 ]; then ... fi` block shown in Step 1 (i.e., right after its closing `fi`, before the `# ── 유틸:` comment that currently follows it):

```bash
# GitHub PAT for .mcp/서연.json, .mcp/태양.json (${GITHUB_PAT} reference).
# Missing .env just means those two panes' github MCP fails to connect --
# does not block team startup.
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi
```

- [ ] **Step 3: Add `mcp_config` array population**

Immediately after the `.env`-loading block from Step 2, add (bash-3.2-compatible `while read` pattern, matching Task A's established style — no `readarray`):

```bash
MEMBER_MCP_CONFIGS=()
while IFS= read -r line; do
    MEMBER_MCP_CONFIGS+=("$line")
done < <(python3 -c "
import yaml
try:
    with open('team.yaml') as f:
        data = yaml.safe_load(f)
    for m in sorted(data['team'], key=lambda x: x['pane']):
        print(m.get('mcp_config') or '')
except Exception:
    pass
" 2>/dev/null)
```

(No hardcoded fallback array needed here — an empty `MEMBER_MCP_CONFIGS[$i]` for every index is exactly the "no MCP for this pane" state, which Step 4's conditional already treats as a no-op.)

- [ ] **Step 4: Make the pane-launch command conditional on `MEMBER_MCP_CONFIGS[$i]`**

Using `Edit`, replace this exact block (lines 141-142, shown in Step 1):

```bash
    tmux send-keys -t "$pane" \
        "cd '$WORKDIR' && unset CLAUDECODE && $CLAUDE_BIN --model ${MEMBER_MODELS[$i]} --dangerously-skip-permissions" Enter
```

with:

```bash
    if [ -n "${MEMBER_MCP_CONFIGS[$i]:-}" ]; then
        tmux send-keys -t "$pane" \
            "cd '$WORKDIR' && unset CLAUDECODE && $CLAUDE_BIN --model ${MEMBER_MODELS[$i]} --mcp-config '${MEMBER_MCP_CONFIGS[$i]}' --strict-mcp-config --dangerously-skip-permissions" Enter
    else
        tmux send-keys -t "$pane" \
            "cd '$WORKDIR' && unset CLAUDECODE && $CLAUDE_BIN --model ${MEMBER_MODELS[$i]} --dangerously-skip-permissions" Enter
    fi
```

This stays inside the same `for i in 0 1 2 3 4 5; do ... done` loop (lines 137-143) — only the two lines building the `tmux send-keys` command change; the surrounding `tmux send-keys -t "$pane" C-c` and `sleep 0.1` lines above it, and the loop's `done` below it, are untouched.

- [ ] **Step 5: Verify bash syntax is still valid**

Run: `cd /Users/syj/workspaces/multi-agent && bash -n setup-team-v2.sh`
Expected: no output (silent success)

- [ ] **Step 6: Dry-run the `mcp_config` array population in isolation**

Run:
```bash
cd /Users/syj/workspaces/multi-agent && bash -c '
MEMBER_MCP_CONFIGS=()
while IFS= read -r line; do
    MEMBER_MCP_CONFIGS+=("$line")
done < <(python3 -c "
import yaml
with open(\"team.yaml\") as f:
    data = yaml.safe_load(f)
for m in sorted(data[\"team\"], key=lambda x: x[\"pane\"]):
    print(m.get(\"mcp_config\") or \"\")
")
for i in "${!MEMBER_MCP_CONFIGS[@]}"; do
    echo "[$i] -> \"${MEMBER_MCP_CONFIGS[$i]}\""
done
'
```
Expected output (6 lines, indices 0-5 matching 쭌/민준/지훈/수아/서연/태양 pane order):
```
[0] -> ""
[1] -> ".mcp/민준.json"
[2] -> ""
[3] -> ".mcp/수아.json"
[4] -> ".mcp/서연.json"
[5] -> ".mcp/태양.json"
```

- [ ] **Step 7: Verify `.env` loading in isolation (without touching the real `.env` or leaking its value)**

Run:
```bash
cd /Users/syj/workspaces/multi-agent && bash -c '
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi
if [ -n "${GITHUB_PAT:-}" ]; then
    echo "GITHUB_PAT is set (length: ${#GITHUB_PAT})"
else
    echo "GITHUB_PAT is NOT set"
fi
'
```
Expected: `GITHUB_PAT is set (length: N)` for some `N > 0` — confirms the `.env` loads and populates the variable, without printing the value itself.

- [ ] **Step 8: Commit**

```bash
cd /Users/syj/workspaces/multi-agent
git add setup-team-v2.sh
git commit -m "feat: setup-team-v2.sh loads .env and passes --mcp-config/--strict-mcp-config per persona"
```

---

### Task 4: Live smoke test (outside this repo)

**Files:** none created or modified — verification-only task.

**Interfaces:** none.

- [ ] **Step 1: Copy one config file to an isolated temp directory**

Run:
```bash
mkdir -p /tmp/mcp-smoke-test
cp /Users/syj/workspaces/multi-agent/.mcp/민준.json /tmp/mcp-smoke-test/
cd /tmp/mcp-smoke-test
```

`/tmp/mcp-smoke-test` has no `.claude/settings.json`, so this avoids the Track B `Stop`-hook side effect documented in this plan's Global Constraints.

- [ ] **Step 2: Run a one-shot session with the isolated config**

Run (from `/tmp/mcp-smoke-test`, NOT from the repo):
```bash
claude --mcp-config 민준.json --strict-mcp-config -p "List the exact tool names available to you that come from an MCP server (names containing 'mcp__'). Just list names, one per line, nothing else." 2>&1
```

Expected: output lists only `context7`-derived tool names (e.g. names containing `context7`) — no `github`, `gsd`, `browser`, or other unrelated MCP tool names appear. First run may take longer than usual (`npx` downloads `@upstash/context7-mcp` on first invocation).

- [ ] **Step 3: Clean up**

Run: `rm -rf /tmp/mcp-smoke-test`

- [ ] **Step 4: Record the result**

No commit for this task (nothing was created in the repo). Record the smoke-test output (pass/fail, which tool names appeared) in the SDD progress ledger for this branch as evidence the `--mcp-config`/`--strict-mcp-config` mechanism works end-to-end with a real config file from this repo.

---

## Explicitly deferred (per spec's 제외 범위)

- Giving 지훈/쭌 MCP servers now — native `WebSearch`/`WebFetch` covers 지훈's current need; add later if insufficient.
- Rotating/cleaning up the existing plaintext GitHub token in `~/.claude.json`'s global project MCP entry — user's call, outside this repo.
- Automatic retry/fallback if an MCP server fails to connect — left to Claude Code's default behavior.
- Pre-installing `context7`/`playwright-mcp` npm packages to avoid first-run `npx` download latency.
- Extending this mechanism to non-development personas ("일상생활 관리" etc.) — separate future track.
