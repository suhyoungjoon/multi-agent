import re
from pathlib import Path

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


def load_team(script_path: Path = DEFAULT_SCRIPT_PATH) -> list[dict]:
    """Load the team roster from setup-team-v2.sh's bash arrays.

    Falls back to the hardcoded 6-member roster if the script is
    missing, unreadable, or doesn't define MEMBER_NAMES — this is the
    team.yaml placeholder until that schema exists (see spec §team_config.py).
    """
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
