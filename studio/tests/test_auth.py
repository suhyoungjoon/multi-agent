import pytest
from fastapi import HTTPException

from studio import auth


def test_require_token_raises_401_when_missing(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_token(x_studio_token="")
    assert exc_info.value.status_code == 401


def test_require_token_raises_401_when_wrong(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        auth.require_token(x_studio_token="wrong")
    assert exc_info.value.status_code == 401


def test_require_token_passes_when_correct(monkeypatch):
    monkeypatch.setenv("STUDIO_TOKEN", "secret123")
    auth.require_token(x_studio_token="secret123")  # should not raise
