import httpx
import pytest

import app
from app.web.app import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_returns_ok_and_version() -> None:
    # httpx's ASGITransport instead of starlette's TestClient: the latter's type hints
    # point at the optional httpx2 package, which breaks pyright strict.
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": app.__version__}
