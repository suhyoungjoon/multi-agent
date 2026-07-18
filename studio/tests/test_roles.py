from pathlib import Path

from studio import roles

FIXTURE_YAML = '''
team:
  - name: 쭌
    pane: 0
    role: |
      너는 쭌, 팀장이다.
  - name: 민준
    pane: 1
    role: |
      너는 민준, 아키텍트다.
'''


def test_load_roles_parses_pane_index_to_text(tmp_path: Path):
    team_yaml = tmp_path / "team.yaml"
    team_yaml.write_text(FIXTURE_YAML, encoding="utf-8")

    loaded = roles.load_roles(team_yaml)

    assert loaded[0] == "너는 쭌, 팀장이다.\n"
    assert loaded[1] == "너는 민준, 아키텍트다.\n"


def test_load_roles_returns_empty_dict_when_file_missing(tmp_path: Path):
    missing = tmp_path / "nope.yaml"

    loaded = roles.load_roles(missing)

    assert loaded == {}


def test_default_team_yaml_has_six_role_entries():
    loaded = roles.load_roles()

    assert set(loaded.keys()) == {0, 1, 2, 3, 4, 5}
    assert "쭌" in loaded[0]


def test_load_roles_returns_empty_dict_when_yaml_is_a_list(tmp_path: Path):
    team_yaml = tmp_path / "team.yaml"
    team_yaml.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    loaded = roles.load_roles(team_yaml)

    assert loaded == {}


def test_load_roles_returns_empty_dict_when_yaml_is_a_scalar(tmp_path: Path):
    team_yaml = tmp_path / "team.yaml"
    team_yaml.write_text("just a string\n", encoding="utf-8")

    loaded = roles.load_roles(team_yaml)

    assert loaded == {}


def test_load_roles_returns_empty_dict_when_team_key_missing(tmp_path: Path):
    team_yaml = tmp_path / "team.yaml"
    team_yaml.write_text("not_team: []\n", encoding="utf-8")

    loaded = roles.load_roles(team_yaml)

    assert loaded == {}


def test_load_roles_skips_members_missing_pane_or_role(tmp_path: Path):
    team_yaml = tmp_path / "team.yaml"
    team_yaml.write_text(
        '''
team:
  - name: 쭌
    pane: 0
    role: "너는 쭌이다."
  - name: 이상함
    role: "pane 없음"
  - name: 이상함2
    pane: 2
''',
        encoding="utf-8",
    )

    loaded = roles.load_roles(team_yaml)

    assert loaded == {0: "너는 쭌이다."}
