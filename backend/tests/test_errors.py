import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    DomainError,
    InsufficientStockError,
    NotFoundError,
    error_body,
    register_exception_handlers,
)


def _app_with(routes) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    for path, handler in routes:
        app.get(path)(handler)
    return app


async def _get(app: FastAPI, path: str):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.get(path)


@pytest.mark.anyio
async def test_domain_error_renders_unified_shape():
    async def boom():
        raise NotFoundError(message="product not found", code="PRODUCT_NOT_FOUND")

    response = await _get(_app_with([("/boom", boom)]), "/boom")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "PRODUCT_NOT_FOUND", "message": "product not found", "details": {}}
    }


@pytest.mark.anyio
async def test_domain_error_carries_details():
    async def boom():
        raise InsufficientStockError(
            message="not enough stock",
            details={"variant_id": "v1", "available": 1},
        )

    response = await _get(_app_with([("/boom", boom)]), "/boom")
    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "INSUFFICIENT_STOCK"
    assert body["details"] == {"variant_id": "v1", "available": 1}


@pytest.mark.anyio
async def test_unhandled_error_is_masked():
    async def boom():
        raise RuntimeError("database password is hunter2")

    response = await _get(_app_with([("/boom", boom)]), "/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text


def test_error_body_helper():
    assert error_body("X", "y") == {"error": {"code": "X", "message": "y", "details": {}}}


def test_subclasses_set_status_and_code():
    assert (NotFoundError.code, NotFoundError.status_code) == ("NOT_FOUND", 404)
    assert issubclass(NotFoundError, DomainError)
