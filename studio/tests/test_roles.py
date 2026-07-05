from pathlib import Path

from studio import roles

FIXTURE_YAML = """
0: |
  너는 쭌, 팀장이다.
1: |
  너는 민준, 아키텍트다.
"""


def test_load_roles_parses_pane_index_to_text(tmp_path: Path):
    roles_file = tmp_path / "roles.yaml"
    roles_file.write_text(FIXTURE_YAML, encoding="utf-8")

    loaded = roles.load_roles(roles_file)

    assert loaded[0] == "너는 쭌, 팀장이다.\n"
    assert loaded[1] == "너는 민준, 아키텍트다.\n"


def test_load_roles_returns_empty_dict_when_file_missing(tmp_path: Path):
    missing = tmp_path / "nope.yaml"

    loaded = roles.load_roles(missing)

    assert loaded == {}


def test_default_roles_yaml_has_six_entries():
    loaded = roles.load_roles()

    assert set(loaded.keys()) == {0, 1, 2, 3, 4, 5}
    assert "쭌" in loaded[0]
