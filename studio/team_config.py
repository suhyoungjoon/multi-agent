import re
from pathlib import Path

import yaml

DEFAULT_YAML_PATH = Path(__file__).resolve().parent.parent / "team.yaml"
DEFAULT_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "setup-team-v2.sh"

_FALLBACK_NAMES = ["쭌", "민준 아키텍트", "지훈 리서쳐", "수아 UI/UX디자이너", "서연 개발자", "태양 QA·리뷰어"]
_FALLBACK_MODEL = "claude-sonnet-4-6"


def _extract_array(script_text: str, var_name: str) -> list[str]:
    match = re.search(rf'{var_name}=\((.*?)\)', script_text, re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]*)"', match.group(1))


def _fallback_team() -> list[dict]:
    return [
        {"pane": idx, "name": name, "model": _FALLBACK_MODEL}
        for idx, name in enumerate(_FALLBACK_NAMES)
    ]


def _load_from_yaml(yaml_path: Path) -> list[dict] | None:
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("team"), list):
        return None
    members = [m for m in data["team"] if isinstance(m, dict) and "pane" in m]
    if not members:
        return None
    return sorted(members, key=lambda m: m["pane"])


def _load_from_script(script_path: Path) -> list[dict]:
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return _fallback_team()

    names = _extract_array(text, "MEMBER_NAMES")
    if not names:
        return _fallback_team()

    models = _extract_array(text, "MEMBER_MODELS")
    team = []
    for idx, name in enumerate(names):
        model = models[idx] if idx < len(models) else _FALLBACK_MODEL
        team.append({"pane": idx, "name": name, "model": model})
    return team


def load_team(
    yaml_path: Path = DEFAULT_YAML_PATH,
    script_path: Path = DEFAULT_SCRIPT_PATH,
) -> list[dict]:
    """Load the team roster.

    Tries team.yaml first (single source of truth). Falls back to
    parsing setup-team-v2.sh's bash arrays if team.yaml is missing or
    malformed, and finally falls back to a hardcoded 6-member roster —
    never raises, so a missing/broken team.yaml never blocks the team.
    """
    from_yaml = _load_from_yaml(yaml_path)
    if from_yaml is not None:
        return from_yaml
    return _load_from_script(script_path)
