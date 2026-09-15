import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.anyio
async def test_healthz():
    application = create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        response = await ac.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readyz_reports_subsystems():
    application = create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        response = await ac.get("/readyz")
    body = response.json()
    assert response.status_code == 200
    assert "db" in body and "redis" in body


@pytest.mark.anyio
async def test_openapi_is_served():
    application = create_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        response = await ac.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"].startswith("NeoStore")
