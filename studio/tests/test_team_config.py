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


def test_load_team_parses_names_and_models(tmp_path: Path):
    script = tmp_path / "setup-team-v2.sh"
    script.write_text(FIXTURE_SCRIPT, encoding="utf-8")

    team = team_config.load_team(script)

    assert team == [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준 아키텍트", "model": "claude-sonnet-4-6"},
        {"pane": 2, "name": "지훈 리서쳐", "model": "claude-opus-4-8"},
    ]


def test_load_team_falls_back_when_script_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist.sh"

    team = team_config.load_team(missing)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"
    assert all("model" in member for member in team)


def test_load_team_falls_back_when_arrays_absent(tmp_path: Path):
    script = tmp_path / "empty.sh"
    script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

    team = team_config.load_team(script)

    assert len(team) == 6
    assert team[0]["name"] == "쭌"


def test_load_team_uses_fallback_model_when_more_names_than_models(tmp_path: Path):
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

    team = team_config.load_team(script)

    assert team == [
        {"pane": 0, "name": "쭌", "model": "claude-sonnet-4-6"},
        {"pane": 1, "name": "민준 아키텍트", "model": "claude-opus-4-8"},
        {"pane": 2, "name": "지훈 리서쳐", "model": team_config._FALLBACK_MODEL},
        {"pane": 3, "name": "추가 멤버", "model": team_config._FALLBACK_MODEL},
    ]
