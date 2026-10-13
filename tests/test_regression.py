
import copy
import json

import pytest
import yaml

from app.adapters.http_results import to_http_response
from app.models import Endpoint
from app.application.context_builder import ContextBuilder
from app.application.response_generation import ResponseGenerationService
from app.application.session_resources import SessionResources
from app.application.simulation_engine import SimulationEngine
from app.application.validator import PayloadValidator


class FakeSessionStore:
    def __init__(self):
        self.sessions = {}

    async def initialize(self):
        pass

    async def get_session(self, session_id):
        state = self.sessions.get(session_id)
        return copy.deepcopy(state) if state is not None else None

    async def save_session(self, session_id, state):
        self.sessions[session_id] = copy.deepcopy(state)

    async def delete_session(self, session_id):
        self.sessions.pop(session_id, None)


class FakeLogger:
    def __init__(self):
        self.records = []

    async def log(
        self,
        path,
        method,
        result,
        latency_ms=None,
        session_id=None,
    ):
        self.records.append({
            "path": path,
            "method": method,
            "status_code": to_http_response(result)[0],
            "latency_ms": latency_ms,
            "valid": result.failure is None,
            "fallback": False,
            "session_id": session_id,
        })


class FakeResponseGenerator:
    async def generate(self, context):
        raise AssertionError(
            "O Gemini real não deve ser chamado nos testes."
        )


@pytest.fixture
def environment():
    with open("contracts/test-api.yaml", encoding="utf-8") as file:
        contract = yaml.safe_load(file)

    endpoints = []

    for path, operations in contract["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in {
                "get", "post", "put", "patch", "delete"
            }:
                continue

            endpoints.append(
                Endpoint(
                    path=path,
                    method=method.upper(),
                    summary=operation.get("summary"),
                    parameters=[
                        {
                            "name": parameter["name"],
                            "location": parameter["in"],
                            "required": parameter.get("required", False),
                            "schema": parameter.get("schema", {}),
                        }
                        for parameter in operation.get("parameters", [])
                    ],
                    request_body=operation.get("requestBody"),
                    responses=operation.get("responses", {}),
                )
            )

    sessions = FakeSessionStore()
    session_resources = SessionResources(sessions)
    logger = FakeLogger()
    validator = PayloadValidator()
    response_generator = FakeResponseGenerator()
    response_generation = ResponseGenerationService(
        response_generator,
        validator,
        session_resources,
    )

    engine = SimulationEngine(
        endpoints=endpoints,
        context_builder=ContextBuilder(contract),
        session_resources=session_resources,
        response_generation=response_generation,
        validator=validator,
        request_logger=logger,
    )

    return engine, sessions, logger


def mock_responses(monkeypatch, engine, responses):
    queue = iter(copy.deepcopy(responses))
    calls = []

    async def fake_generate(context):
        calls.append(context)

        try:
            return json.dumps(next(queue))
        except StopIteration:
            raise AssertionError(
                "O motor fez mais chamadas do que o esperado."
            )

    monkeypatch.setattr(
        engine.response_generation.response_generator,
        "generate",
        fake_generate,
    )

    return calls


def order_data(order_id=101, total=175, status="created"):
    return {
        "id": order_id,
        "customer_name": "Cliente Teste",
        "total": total,
        "status": status,
    }


def payment_data(payment_id=201, status="pending"):
    return {
        "id": payment_id,
        "order_id": 101,
        "amount": 175,
        "method": "credit_card",
        "status": status,
    }


@pytest.mark.asyncio
async def test_criacao_e_consulta_de_pedido(environment, monkeypatch):
    engine, sessions, logger = environment

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data()],
    )

    created = await simulate_http(engine,
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": 175,
        },
        session_id="sessaoA",
    )

    assert created["status_code"] == 201
    assert created["data"] == order_data()

    consulted = await simulate_http(engine,
        "/orders/{id}",
        "GET",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    assert consulted["status_code"] == 200
    assert consulted["data"] == order_data()
    assert len(calls) == 1
    assert len(logger.records) == 2


@pytest.mark.asyncio
async def test_isolamento_entre_sessoes(environment, monkeypatch):
    engine, sessions, logger = environment

    mock_responses(monkeypatch, engine, [order_data()])

    await simulate_http(engine,
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": 175,
        },
        session_id="sessaoA",
    )

    result = await simulate_http(engine,
        "/orders/{id}",
        "GET",
        parameters={"id": 101},
        session_id="sessaoB",
    )

    assert result["status_code"] == 404
    assert await sessions.get_session("sessaoB") is None


@pytest.mark.asyncio
async def test_cancelamento_preserva_dados(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"orders": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data(total=9999, status="cancelled")],
    )

    result = await simulate_http(engine,
        "/orders/{id}/cancel",
        "POST",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    stored = await sessions.get_session("sessaoA")
    saved_order = stored["orders"]["101"]

    assert result["status_code"] == 200
    assert result["data"]["total"] == 175
    assert result["data"]["status"] == "cancelled"
    assert saved_order == result["data"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_criacao_e_confirmacao_pagamento(
    environment, monkeypatch
):
    engine, sessions, logger = environment

    mock_responses(
        monkeypatch,
        engine,
        [
            payment_data(),
            {
                "id": 201,
                "order_id": 101,
                "status": "confirmed",
            },
        ],
    )

    created = await simulate_http(engine,
        "/payments",
        "POST",
        request_body={
            "order_id": 101,
            "amount": 175,
            "method": "credit_card",
        },
        session_id="sessaoA",
    )

    assert created["status_code"] == 201

    confirmed = await simulate_http(engine,
        "/payments/{id}/confirm",
        "POST",
        parameters={"id": 201},
        session_id="sessaoA",
    )

    assert confirmed["status_code"] == 200
    assert confirmed["data"]["status"] == "confirmed"
    assert confirmed["data"]["amount"] == 175
    assert confirmed["data"]["method"] == "credit_card"

    consulted = await simulate_http(engine,
        "/payments/{id}",
        "GET",
        parameters={"id": 201},
        session_id="sessaoA",
    )

    assert consulted["status_code"] == 200
    assert consulted["data"] == confirmed["data"]


@pytest.mark.asyncio
async def test_validacao_do_request_body(environment, monkeypatch):
    engine, sessions, logger = environment

    calls = mock_responses(monkeypatch, engine, [])

    result = await simulate_http(engine,
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": "valor_invalido",
        },
        session_id="sessaoA",
    )

    assert result["status_code"] == 400
    assert len(calls) == 0
    assert await sessions.get_session("sessaoA") is None


@pytest.mark.asyncio
async def test_resposta_invalida_apos_tres_tentativas(
    environment, monkeypatch
):
    engine, sessions, logger = environment

    calls = mock_responses(
        monkeypatch,
        engine,
        [None, None, None],
    )

    result = await simulate_http(engine,
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": 175,
        },
        session_id="sessaoA",
    )

    assert result["status_code"] == 503
    assert "data" not in result
    assert len(calls) == 3
    assert await sessions.get_session("sessaoA") is None


@pytest.mark.asyncio
async def test_id_incorreto_na_resposta(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"orders": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [
            order_data(999, status="cancelled"),
            order_data(999, status="cancelled"),
            order_data(999, status="cancelled"),
        ],
    )

    result = await simulate_http(engine,
        "/orders/{id}/cancel",
        "POST",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    state = await sessions.get_session("sessaoA")

    assert result["status_code"] == 503
    assert len(calls) == 3
    assert state["orders"]["101"] == order_data()
    assert "999" not in state["orders"]


@pytest.mark.asyncio
async def test_colisao_de_id_na_criacao(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"orders": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data(), order_data(), order_data()],
    )

    result = await simulate_http(engine,
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": 175,
        },
        session_id="sessaoA",
    )

    state = await sessions.get_session("sessaoA")

    assert result["status_code"] == 503
    assert len(calls) == 3
    assert state["orders"]["101"] == order_data()
    assert len(state["orders"]) == 1


async def simulate_http(engine, *args, **kwargs):
    result = await engine.simulate(*args, **kwargs)
    return to_http_response(result)[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure, expected_kind, expected_status", [
    ("timeout", "generation_timeout", 503),
    ("quota", "generation_rate_limited", 429),
    ("unavailable", "generation_unavailable", 503),
])
async def test_generator_failures_are_transport_independent(
    environment, monkeypatch, failure, expected_kind, expected_status,
):
    from app.application.ports import GenerationRateLimited, GenerationTimeout

    engine, sessions, logger = environment
    exceptions = {
        "timeout": GenerationTimeout(),
        "quota": GenerationRateLimited(),
        "unavailable": RuntimeError("provider-specific detail"),
    }

    async def fail(context):
        raise exceptions[failure]

    monkeypatch.setattr(engine.response_generation.response_generator, "generate", fail)
    result = await engine.simulate(
        "/orders", "POST",
        request_body={"customer_name": "Cliente Teste", "total": 175},
        session_id="sessaoA",
    )
    assert result.failure.kind.value == expected_kind
    assert "Gemini" not in result.failure.message
    assert to_http_response(result)[0] == expected_status
    assert await sessions.get_session("sessaoA") is None
    assert logger.records[0]["valid"] is False


@pytest.mark.asyncio
async def test_http_flow_preserves_envelope_and_maps_failures(environment, monkeypatch):
    import httpx
    from app.adapters.http_api import create_http_app

    engine, sessions, logger = environment
    mock_responses(monkeypatch, engine, [order_data()])
    app = create_http_app(list(engine.endpoints.values()), engine, lifespan=None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        created = await client.post(
            "/orders", json={"customer_name": "Cliente Teste", "total": 175},
            headers={"X-Session-ID": "sessaoA"},
        )
        assert created.status_code == 201
        assert created.json()["data"] == order_data()
        assert created.json()["context"]["endpoint"]["path"] == "/orders"
        found = await client.get("/orders/101", headers={"X-Session-ID": "sessaoA"})
        assert found.status_code == 200
        assert found.json()["data"] == order_data()
        missing = await client.get("/orders/101", headers={"X-Session-ID": "sessaoB"})
        assert missing.status_code == 404
        assert missing.json() == {
            "status_code": 404, "message": "Recurso não encontrado na sessão",
        }
        invalid = await client.post("/orders", json={"customer_name": "Teste", "total": "x"})
        assert invalid.status_code == 400
        invalid_parameter = await client.get("/orders/abc")
        assert invalid_parameter.status_code == 422
