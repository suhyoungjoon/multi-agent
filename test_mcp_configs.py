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
