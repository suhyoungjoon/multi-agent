from pathlib import Path

import yaml

DEFAULT_TEAM_YAML_PATH = Path(__file__).resolve().parent.parent / "team.yaml"


def load_roles(path: Path = DEFAULT_TEAM_YAML_PATH) -> dict[int, str]:
    """Load pane-index -> role-instruction-text mapping from team.yaml.

    Returns an empty dict if the file is missing or malformed, rather
    than raising — callers (main.py's restart_pane) treat an empty
    dict as "role reinject unavailable for this pane" and respond 404
    instead of crashing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict) or not isinstance(data.get("team"), list):
        return {}

    result: dict[int, str] = {}
    for member in data["team"]:
        if not isinstance(member, dict):
            continue
        pane = member.get("pane")
        role = member.get("role")
        if isinstance(pane, int) and isinstance(role, str):
            result[pane] = role
    return result
