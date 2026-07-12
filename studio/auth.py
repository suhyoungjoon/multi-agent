import os

from fastapi import Header, HTTPException


def require_token(x_studio_token: str = Header(default="")) -> None:
    """FastAPI dependency guarding every /api route from LAN access.

    Reads STUDIO_TOKEN fresh from the environment on every call (not
    cached at import time) so tests can monkeypatch it per-case.
    """
    expected = os.environ.get("STUDIO_TOKEN", "")
    if not expected or x_studio_token != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-Studio-Token header")
