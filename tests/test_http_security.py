from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.http_api import create_http_app
from app.adapters.openapi_parser import get_endpoints, parse_openapi
from app.application.results import SimulationResult


@pytest.fixture
def setup_app(monkeypatch):
    for name in ("SIMULATOR_AUTH_ENABLED", "SIMULATOR_ACCESS_KEY", "SIMULATOR_DEBUG_ENABLED"):
        monkeypatch.delenv(name, raising=False)

    def build():
        engine = AsyncMock()
        engine.simulate.return_value = SimulationResult(
            response_key="200", data={"id": 101},
            context={"session_state": {"private": "session-data"}},
        )
        app = create_http_app(
            get_endpoints(parse_openapi("contracts/test-api.yaml")), engine, None,
        )
        return app, engine

    return build


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "incorrect"}])
@pytest.mark.parametrize("method,path,body", [
    ("GET", "/pedidos/101", None),
    ("POST", "/pedidos", {"nome_cliente": "Maria", "itens": []}),
])
async def test_denied_before_engine(setup_app, monkeypatch, headers, method, path, body):
    monkeypatch.setenv("SIMULATOR_AUTH_ENABLED", "true")
    monkeypatch.setenv("SIMULATOR_ACCESS_KEY", "test-only-secret")
    app, engine = setup_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path, headers=headers, json=body)
    assert response.status_code == 401
    assert "test-only-secret" not in response.text
    assert "incorrect" not in response.text
    engine.simulate.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_and_public_swagger(setup_app, monkeypatch):
    monkeypatch.setenv("SIMULATOR_AUTH_ENABLED", "true")
    monkeypatch.setenv("SIMULATOR_ACCESS_KEY", "test-only-secret")
    app, engine = setup_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/", "/docs", "/openapi.json"):
            response = await client.get(path)
            assert response.status_code == 200
            assert "test-only-secret" not in response.text
        engine.simulate.assert_not_awaited()
        schema = (await client.get("/openapi.json")).json()
        scheme = schema["components"]["securitySchemes"]["APIKeyHeader"]
        assert scheme == {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        assert schema["paths"]["/pedidos/{id}"]["get"]["security"] == [{"APIKeyHeader": []}]
        response = await client.get("/pedidos/101", headers={
            "X-API-Key": "test-only-secret", "X-Session-ID": "demo", "X-Debug": "true",
        })
    assert response.status_code == 200
    assert "diagnostico" not in response.json()
    assert "session-data" not in response.text
    assert "test-only-secret" not in response.text
    engine.simulate.assert_awaited_once_with("/pedidos/{id}", "GET", {"id": "101"}, None, "demo")


@pytest.mark.asyncio
@pytest.mark.parametrize("auth,debug,expected", [
    (False, None, True), (False, "false", False),
    (True, "false", False), (True, "true", True),
])
async def test_debug_configuration(setup_app, monkeypatch, auth, debug, expected):
    monkeypatch.setenv("SIMULATOR_AUTH_ENABLED", str(auth).lower())
    monkeypatch.setenv("SIMULATOR_ACCESS_KEY", "test-only-secret")
    if debug is not None:
        monkeypatch.setenv("SIMULATOR_DEBUG_ENABLED", debug)
    app, engine = setup_app()
    headers = {"X-Debug": "true"}
    if auth:
        headers["X-API-Key"] = "test-only-secret"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/pedidos/101", headers=headers)
    assert response.status_code == 200
    assert ("diagnostico" in response.json()) is expected
    engine.simulate.assert_awaited_once()


@pytest.mark.parametrize("key", [None, "", "   "])
def test_protection_requires_key(setup_app, monkeypatch, key):
    monkeypatch.setenv("SIMULATOR_AUTH_ENABLED", "true")
    if key is not None:
        monkeypatch.setenv("SIMULATOR_ACCESS_KEY", key)
    with pytest.raises(ValueError, match="SIMULATOR_ACCESS_KEY"):
        setup_app()


@pytest.mark.parametrize("name", ["SIMULATOR_AUTH_ENABLED", "SIMULATOR_DEBUG_ENABLED"])
def test_invalid_flag_rejected(setup_app, monkeypatch, name):
    monkeypatch.setenv(name, "invalid")
    with pytest.raises(ValueError, match=name):
        setup_app()
