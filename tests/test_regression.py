
import copy

import pytest
import yaml

from app.models import Endpoint
from app import simulation_engine


class FakeSessionManager:
    def __init__(self):
        self.sessions = {}

    async def get_session(self, session_id):
        state = self.sessions.get(session_id)
        return copy.deepcopy(state) if state is not None else None

    async def save_session(self, session_id, state):
        self.sessions[session_id] = copy.deepcopy(state)


class FakeLogger:
    def __init__(self):
        self.records = []

    async def log(self, **kwargs):
        self.records.append(kwargs)


class FakeLLMAdapter:
    async def generate(self, context):
        raise AssertionError(
            "O Gemini real não deve ser chamado nos testes."
        )


@pytest.fixture
def environment(monkeypatch):
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

    monkeypatch.setattr(
        simulation_engine,
        "LLMAdapter",
        FakeLLMAdapter,
    )

    sessions = FakeSessionManager()
    logger = FakeLogger()

    engine = simulation_engine.SimulationEngine(
        endpoints=endpoints,
        contract=contract,
        session_manager=sessions,
        request_logger=logger,
    )

    return engine, sessions, logger


def mock_responses(monkeypatch, engine, responses):
    queue = iter(copy.deepcopy(responses))
    calls = []

    async def fake_generate(context):
        calls.append(context)

        try:
            return next(queue)
        except StopIteration:
            raise AssertionError(
                "O motor fez mais chamadas do que o esperado."
            )

    monkeypatch.setattr(
        engine,
        "generate_response",
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

    created = await engine.simulate(
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

    consulted = await engine.simulate(
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

    await engine.simulate(
        "/orders",
        "POST",
        request_body={
            "customer_name": "Cliente Teste",
            "total": 175,
        },
        session_id="sessaoA",
    )

    result = await engine.simulate(
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

    result = await engine.simulate(
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

    created = await engine.simulate(
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

    confirmed = await engine.simulate(
        "/payments/{id}/confirm",
        "POST",
        parameters={"id": 201},
        session_id="sessaoA",
    )

    assert confirmed["status_code"] == 200
    assert confirmed["data"]["status"] == "confirmed"
    assert confirmed["data"]["amount"] == 175
    assert confirmed["data"]["method"] == "credit_card"

    consulted = await engine.simulate(
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

    result = await engine.simulate(
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

    result = await engine.simulate(
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

    result = await engine.simulate(
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

    result = await engine.simulate(
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
