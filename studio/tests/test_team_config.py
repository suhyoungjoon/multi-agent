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

FIXTURE_YAML = '''
team:
  - name: 쭌
    pane: 0
    model: claude-sonnet-4-6
    role: "너는 쭌이다."
    reports_to: null
    outputs: []
    hub_for: []
    owns_files: []
  - name: 민준
    pane: 1
    model: claude-opus-4-8
    role: "너는 민준이다."
    reports_to: 쭌
    outputs: []
    hub_for: []
    owns_files: []
'''


def test_load_team_reads_from_yaml_when_present(tmp_path: Path):
    yaml_file = tmp_path / "team.yaml"
    yaml_file.write_text(FIXTURE_YAML, encoding="utf-8")
    missing_script = tmp_path / "does-not-exist.sh"

    team = team_config.load_team(yaml_path=yaml_file, script_path=missing_script)

    assert [m["name"] for m in team] == ["쭌", "민준"]
    assert team[1]["model"] == "claude-opus-4-8"
    assert team[1]["reports_to"] == "쭌"


def test_load_team_sorts_by_pane_regardless_of_yaml_order(tmp_path: Path):
    yaml_file = tmp_path / "team.yaml"
    yaml_file.write_text(
        '''
team:
  - name: 민준
    pane: 1
    model: claude-sonnet-4-6
  - name: 쭌
    pane: 0
    model: claude-sonnet-4-6
''',
        encoding="utf-8",
    )

    team = team_config.load_team(yaml_path=yaml_file, script_path=tmp_path / "nope.sh")

    assert [m["name"] for m in team] == ["쭌", "민준"]


def test_load_team_prefers_yaml_over_script_when_both_present(tmp_path: Path):
    yaml_file = tmp_path / "team.yaml"
    yaml_file.write_text(FIXTURE_YAML, encoding="utf-8")
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(yaml_path=yaml_file, script_path=script)

    # FIXTURE_YAML has 2 members, FIXTURE_SCRIPT has 3 -- length 2 proves
    # yaml won, not the script fallback.
    assert len(team) == 2


def test_load_team_falls_back_to_script_when_yaml_missing(tmp_path: Path):
    yaml_missing = tmp_path / "team.yaml"
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(yaml_path=yaml_missing, script_path=script)

    assert team == [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준 아키텍트", "model": "claude-sonnet-4-6"},
        {"pane": 2, "name": "지훈 리서쳐", "model": "claude-opus-4-8"},
    ]


def test_load_team_falls_back_to_script_when_yaml_malformed(tmp_path: Path):
    yaml_file = tmp_path / "team.yaml"
    yaml_file.write_text("not: valid: yaml: [structure", encoding="utf-8")
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(yaml_path=yaml_file, script_path=script)

    assert len(team) == 3


def test_load_team_falls_back_to_script_when_yaml_missing_team_key(tmp_path: Path):
    yaml_file = tmp_path / "team.yaml"
    yaml_file.write_text("not_team: []\n", encoding="utf-8")
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(yaml_path=yaml_file, script_path=script)

    assert len(team) == 3


def test_load_team_falls_back_to_hardcoded_when_both_missing(tmp_path: Path):
    yaml_missing = tmp_path / "team.yaml"
    script_missing = tmp_path / "does-not-exist.sh"

    team = team_config.load_team(yaml_path=yaml_missing, script_path=script_missing)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"


def test_load_team_falls_back_when_arrays_absent(tmp_path: Path):
    yaml_missing = tmp_path / "team.yaml"
    script = tmp_path / "empty.sh"
    script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

    team = team_config.load_team(yaml_path=yaml_missing, script_path=script)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"


def test_load_team_uses_fallback_model_when_more_names_than_models(tmp_path: Path):
    yaml_missing = tmp_path / "team.yaml"
    script = tmp_path / "setup-team-extra.sh"
    script.write_text(
        '''#!/bin/bash
MEMBER_NAMES=("쭌" "민준 아키텍트" "지훈 리서쳐" "추가 멤버")
MEMBER_MODELS=(
    "claude-sonnet-4-6"
    "claude-opus-4-8"
)
''',
        encoding="utf-8",
    )

    team = team_config.load_team(yaml_path=yaml_missing, script_path=script)

    assert team == [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준 아키텍트", "model": "claude-opus-4-8"},
        {"pane": 2, "name": "지훈 리서쳐", "model": team_config._FALLBACK_MODEL},
        {"pane": 3, "name": "추가 멤버", "model": team_config._FALLBACK_MODEL},
    ]


def test_default_team_yaml_has_six_members_in_pane_order():
    team = team_config.load_team()

    assert len(team) == 6
    assert [m["name"] for m in team] == ["쭌", "민준", "지훈", "수아", "서연", "태양"]
    assert [m["pane"] for m in team] == [0, 1, 2, 3, 4, 5]


def test_default_team_yaml_has_mcp_config_for_four_members():
    team = team_config.load_team()
    by_name = {m["name"]: m for m in team}

    assert by_name["민준"]["mcp_config"] == ".mcp/민준.json"
    assert by_name["수아"]["mcp_config"] == ".mcp/수아.json"
    assert by_name["서연"]["mcp_config"] == ".mcp/서연.json"
    assert by_name["태양"]["mcp_config"] == ".mcp/태양.json"
    assert by_name["쭌"].get("mcp_config") is None
    assert by_name["지훈"].get("mcp_config") is None
