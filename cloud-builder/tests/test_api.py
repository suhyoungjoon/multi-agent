import pytest
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_generate_aws():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "aws", "app_type": "web",
            "components": ["db"],
            "scale": {"traffic": "medium", "ha": True, "multi_region": False},
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert body["diagram"].startswith("graph TD")
    assert "main.tf" in body["terraform"]


@pytest.mark.asyncio
async def test_generate_azure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "azure", "app_type": "api",
            "components": ["cache"],
            "scale": {"traffic": "low", "ha": False, "multi_region": False},
        })
    assert resp.status_code == 200
    assert "Azure" in resp.json()["summary"]


@pytest.mark.asyncio
async def test_generate_invalid_provider():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "gcp", "app_type": "web",
            "components": [],
            "scale": {"traffic": "low", "ha": False, "multi_region": False},
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_download_terraform_returns_zip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/download/terraform", params={
            "provider": "aws", "app_type": "web",
            "traffic": "low", "ha": "false", "multi_region": "false",
        })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
