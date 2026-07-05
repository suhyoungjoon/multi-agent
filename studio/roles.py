from pathlib import Path

import yaml

DEFAULT_ROLES_PATH = Path(__file__).resolve().parent / "roles.yaml"


def load_roles(path: Path = DEFAULT_ROLES_PATH) -> dict[int, str]:
    """Load pane-index -> role-instruction-text mapping from roles.yaml.

    Returns an empty dict if the file is missing, rather than raising —
    callers (watchdog_loop) treat an empty dict as "role reinject
    unavailable for this pane" and skip the reinject with a logged
    warning instead of crashing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    raw = yaml.safe_load(text) or {}
    return {int(idx): value for idx, value in raw.items()}
