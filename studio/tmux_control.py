import subprocess
import time

SESSION = "team1"


def _pane_target(idx: int, session: str = SESSION) -> str:
    return f"{session}:0.{idx}"


def session_exists(session: str = SESSION) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def capture_pane(idx: int, session: str = SESSION) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", _pane_target(idx, session), "-p"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def send_keys(idx: int, text: str, session: str = SESSION) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", _pane_target(idx, session), text],
        check=False,
    )


def send_enter(idx: int, session: str = SESSION) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", _pane_target(idx, session), "Enter"],
        check=False,
    )


def wake(idx: int, session: str = SESSION) -> None:
    """Resend Enter only — lightweight nudge for a genuinely stuck pane.

    Never called automatically; only ever triggered by a user clicking
    the wake button after checking pane status.
    """
    send_enter(idx, session)


def reinject_role(idx: int, role_text: str, session: str = SESSION) -> None:
    """Resend a pane's role instruction: text, sleep 1.5s, Enter.

    Mirrors watchdog.sh's reinject_role() 3-step send pattern exactly —
    tmux drops input if text and Enter are sent in the same call.
    """
    send_keys(idx, role_text, session)
    time.sleep(1.5)
    send_enter(idx, session)
