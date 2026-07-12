import re

CONTEXT_THRESHOLD_PCT = 70.0
COMPACT_THRESHOLD_PCT = 85.0
CLEAR_DETECTION_FLOOR = 20000

_USAGE_RE = re.compile(r'([\d.]+)(k?)/[\d.]+k?\s*tokens\s*\(([\d.]+)%\)')


def parse_context_usage(screen_text: str) -> tuple[float, int] | None:
    """Parse a `/context` screen for (percent_used, used_tokens).

    Mirrors watchdog.sh's grep -oE pipeline for
    '[0-9.]+k?/[0-9.]+k tokens ([0-9.]+%)'. Returns None if the pattern
    isn't present (e.g. /context hasn't finished rendering yet).
    """
    match = _USAGE_RE.search(screen_text)
    if not match:
        return None
    raw_amount, k_suffix, pct = match.groups()
    used_tokens = float(raw_amount) * 1000 if k_suffix == "k" else float(raw_amount)
    return float(pct), int(used_tokens)
