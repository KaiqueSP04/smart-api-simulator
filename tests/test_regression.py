
import copy
import json

import pytest
import yaml

from app.application.payment_rules import CommerceRules

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
            "codigo_status": to_http_response(result)[0],
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
        for metodo, operation in operations.items():
            if metodo.lower() not in {
                "get", "post", "put", "patch", "delete"
            }:
                continue

            endpoints.append(
                Endpoint(
                    path=path,
                    method=metodo.upper(),
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
        normalizer=CommerceRules(),
    )

    engine = SimulationEngine(
        endpoints=endpoints,
        context_builder=ContextBuilder(contract),
        session_resources=session_resources,
        response_generation=response_generation,
        validator=validator,
        request_logger=logger,
        request_policy=CommerceRules(),
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


def order_data(pedido_id=101, total=175, status="criado"):
    return {
        "id": pedido_id,
        "nome_cliente": "Cliente Teste",
        "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": total}],
        "total": total,
        "situacao": status,
    }


def payment_data(payment_id=201, status="pendente"):
    return {
        "id": payment_id,
        "pedido_id": 101,
        "valor": 175,
        "metodo": "cartao_credito",
        "situacao": status,
    }


@pytest.mark.asyncio
async def test_criacao_e_consulta_de_pedido(environment, monkeypatch):
    engine, sessions, logger = environment

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data()],
    )

    criado = await simulate_http(engine,
        "/pedidos",
        "POST",
        request_body={
            "nome_cliente": "Cliente Teste",
            "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        },
        session_id="sessaoA",
    )

    assert criado["codigo_status"] == 201
    assert criado["dados"] == order_data()

    consulted = await simulate_http(engine,
        "/pedidos/{id}",
        "GET",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    assert consulted["codigo_status"] == 200
    assert consulted["dados"] == order_data()
    assert len(calls) == 1
    assert len(logger.records) == 2


@pytest.mark.asyncio
async def test_isolamento_entre_sessoes(environment, monkeypatch):
    engine, sessions, logger = environment

    mock_responses(monkeypatch, engine, [order_data()])

    await simulate_http(engine,
        "/pedidos",
        "POST",
        request_body={
            "nome_cliente": "Cliente Teste",
            "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        },
        session_id="sessaoA",
    )

    result = await simulate_http(engine,
        "/pedidos/{id}",
        "GET",
        parameters={"id": 101},
        session_id="sessaoB",
    )

    assert result["codigo_status"] == 404
    assert await sessions.get_session("sessaoB") is None


@pytest.mark.asyncio
async def test_cancelamento_preserva_dados(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"pedidos": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data(total=9999, status="cancelado")],
    )

    result = await simulate_http(engine,
        "/pedidos/{id}/cancelar",
        "POST",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    stored = await sessions.get_session("sessaoA")
    saved_order = stored["pedidos"]["101"]

    assert result["codigo_status"] == 200
    assert result["dados"]["total"] == 175
    assert result["dados"]["situacao"] == "cancelado"
    assert saved_order == result["dados"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_criacao_e_confirmacao_pagamento(
    environment, monkeypatch
):
    engine, sessions, logger = environment
    await sessions.save_session("sessaoA", {"pedidos": {"101": order_data()}})

    mock_responses(
        monkeypatch,
        engine,
        [
            payment_data(),
            {
                "id": 201,
                "pedido_id": 101,
                "situacao": "confirmado",
            },
        ],
    )

    criado = await simulate_http(engine,
        "/pagamentos",
        "POST",
        request_body={
            "pedido_id": 101,
            "metodo": "cartao_credito",
        },
        session_id="sessaoA",
    )

    assert criado["codigo_status"] == 201

    confirmado = await simulate_http(engine,
        "/pagamentos/{id}/confirmar",
        "POST",
        parameters={"id": 201},
        session_id="sessaoA",
    )

    assert confirmado["codigo_status"] == 200
    assert confirmado["dados"]["situacao"] == "confirmado"
    assert confirmado["dados"]["valor"] == 175
    assert confirmado["dados"]["metodo"] == "cartao_credito"

    consulted = await simulate_http(engine,
        "/pagamentos/{id}",
        "GET",
        parameters={"id": 201},
        session_id="sessaoA",
    )

    assert consulted["codigo_status"] == 200
    assert consulted["dados"] == confirmado["dados"]


@pytest.mark.asyncio
async def test_validacao_do_request_body(environment, monkeypatch):
    engine, sessions, logger = environment

    calls = mock_responses(monkeypatch, engine, [])

    result = await simulate_http(engine,
        "/pedidos",
        "POST",
        request_body={
            "nome_cliente": "Cliente Teste",
            "total": "valor_invalido",
        },
        session_id="sessaoA",
    )

    assert result["codigo_status"] == 400
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
        "/pedidos",
        "POST",
        request_body={
            "nome_cliente": "Cliente Teste",
            "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        },
        session_id="sessaoA",
    )

    assert result["codigo_status"] == 503
    assert "dados" not in result
    assert len(calls) == 3
    assert await sessions.get_session("sessaoA") is None


@pytest.mark.asyncio
async def test_id_incorreto_na_resposta(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"pedidos": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [
            order_data(999, status="cancelado"),
            order_data(999, status="cancelado"),
            order_data(999, status="cancelado"),
        ],
    )

    result = await simulate_http(engine,
        "/pedidos/{id}/cancelar",
        "POST",
        parameters={"id": 101},
        session_id="sessaoA",
    )

    state = await sessions.get_session("sessaoA")

    assert result["codigo_status"] == 503
    assert len(calls) == 3
    assert state["pedidos"]["101"] == order_data()
    assert "999" not in state["pedidos"]


@pytest.mark.asyncio
async def test_colisao_de_id_na_criacao(environment, monkeypatch):
    engine, sessions, logger = environment

    await sessions.save_session(
        "sessaoA",
        {"pedidos": {"101": order_data()}},
    )

    calls = mock_responses(
        monkeypatch,
        engine,
        [order_data(), order_data(), order_data()],
    )

    result = await simulate_http(engine,
        "/pedidos",
        "POST",
        request_body={
            "nome_cliente": "Cliente Teste",
            "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        },
        session_id="sessaoA",
    )

    state = await sessions.get_session("sessaoA")

    assert result["codigo_status"] == 503
    assert len(calls) == 3
    assert state["pedidos"]["101"] == order_data()
    assert len(state["pedidos"]) == 1


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
        "/pedidos", "POST",
        request_body={"nome_cliente": "Cliente Teste", "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}]},
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
        criado = await client.post(
            "/pedidos", json={"nome_cliente": "Cliente Teste", "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}]},
            headers={"X-Session-ID": "sessaoA"},
        )
        assert criado.status_code == 201
        assert criado.json()["dados"] == order_data()
        assert set(criado.json()) == {"codigo_status", "dados"}
        found = await client.get("/pedidos/101", headers={"X-Session-ID": "sessaoA"})
        assert found.status_code == 200
        assert found.json()["dados"] == order_data()
        missing = await client.get("/pedidos/101", headers={"X-Session-ID": "sessaoB"})
        assert missing.status_code == 404
        assert missing.json() == {
            "codigo_status": 404, "mensagem": "Recurso não encontrado na sessão",
        }
        invalid = await client.post("/pedidos", json={"nome_cliente": "Teste", "itens": []})
        assert invalid.status_code == 400
        invalid_parameter = await client.get("/pedidos/abc")
        assert invalid_parameter.status_code == 422


@pytest.mark.asyncio
async def test_multiple_items_total_is_calculated_and_persisted(environment, monkeypatch):
    engine, sessions, logger = environment
    # Deliberately wrong model output: the application must preserve the request.
    calls = mock_responses(monkeypatch, engine, [{"id": 321, "total": 0, "nome_cliente": "Outro"}])
    items = [
        {"nome_produto": "Mouse sem fio", "quantidade": 2, "preco_unitario": 124.95},
        {"nome_produto": "Teclado", "quantidade": 1, "preco_unitario": 150.0},
    ]
    result = await engine.simulate(
        "/pedidos", "POST", request_body={"nome_cliente": "Maria Silva", "itens": items},
        session_id="compra",
    )
    assert result.failure is None
    assert result.data == {
        "id": 321, "nome_cliente": "Maria Silva", "itens": items,
        "total": 399.9, "situacao": "criado",
    }
    stored = await sessions.get_session("compra")
    assert stored["pedidos"]["321"] == result.data
    consulted = await engine.simulate("/pedidos/{id}", "GET", {"id": 321}, session_id="compra")
    assert consulted.data == result.data
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity, price", [(0, 1), (-1, 1), (1.5, 1), (True, 1), (1, 0), (1, -1), (1, 1.001)])
async def test_invalid_item_rejected_before_generation(environment, monkeypatch, quantity, price):
    engine, sessions, logger = environment
    calls = mock_responses(monkeypatch, engine, [])
    result = await engine.simulate("/pedidos", "POST", request_body={
        "nome_cliente": "Maria", "itens": [
            {"nome_produto": "Mouse", "quantidade": quantity, "preco_unitario": price},
        ],
    })
    assert result.failure.kind.value == "invalid_request"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"nome_cliente": "Maria", "itens": []},
    {"nome_cliente": "  ", "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 1}]},
    {"customer_name": "Maria", "total": 250},
    {"nome_cliente": "Maria", "total": 250, "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 1}]},
])
async def test_invalid_order_shape_rejected(environment, monkeypatch, body):
    engine, sessions, logger = environment
    calls = mock_responses(monkeypatch, engine, [])
    result = await engine.simulate("/pedidos", "POST", request_body=body)
    assert result.failure.kind.value == "invalid_request"
    assert calls == []


@pytest.mark.asyncio
async def test_decimal_total_avoids_float_arithmetic_error(environment, monkeypatch):
    engine, sessions, logger = environment
    mock_responses(monkeypatch, engine, [{"id": 555}])
    result = await engine.simulate("/pedidos", "POST", request_body={
        "nome_cliente": "Maria", "itens": [
            {"nome_produto": "Peça", "quantidade": 3, "preco_unitario": 0.1},
        ],
    })
    assert result.failure is None
    assert result.data["total"] == 0.3


@pytest.mark.asyncio
async def test_debug_header_opt_in_and_swagger_page(environment):
    import httpx
    from app.adapters.http_api import create_http_app

    engine, sessions, logger = environment
    await sessions.save_session("demo", {"pedidos": {"101": order_data()}})
    app = create_http_app(list(engine.endpoints.values()), engine, lifespan=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-Session-ID": "demo"}
        simple = await client.get("/pedidos/101", headers=headers)
        assert set(simple.json()) == {"codigo_status", "dados"}
        detailed = await client.get("/pedidos/101", headers={**headers, "X-Debug": "true"})
        assert detailed.json()["dados"] == simple.json()["dados"]
        assert detailed.json()["diagnostico"]["contexto"]["session_state"] is not None
        disabled = await client.get("/pedidos/101", headers={**headers, "X-Debug": "false"})
        assert disabled.json() == simple.json()
        docs = await client.get("/docs")
        assert docs.status_code == 200
        assert '<html lang="pt-BR">' in docs.text
        assert 'class="docs-banner"' in docs.text
        assert '/openapi.json' in docs.text


@pytest.mark.asyncio
async def test_payment_amount_and_reference_override_model_output(environment, monkeypatch):
    engine, sessions, logger = environment
    await sessions.save_session("compra", {"pedidos": {"101": order_data(total=2555.95)}})
    mock_responses(monkeypatch, engine, [{"id": 201, "pedido_id": 999, "valor": 1, "metodo": "boleto"}])
    result = await engine.simulate("/pagamentos", "POST", request_body={
        "pedido_id": 101, "metodo": "pix",
    }, session_id="compra")
    assert result.failure is None
    assert result.data == {"id": 201, "pedido_id": 101, "valor": 2555.95, "metodo": "pix", "situacao": "pendente"}
    state = await sessions.get_session("compra")
    assert state["pagamentos"]["201"] == result.data


@pytest.mark.asyncio
@pytest.mark.parametrize("session, order, body, expected", [
    (None, order_data(), {"pedido_id": 101, "metodo": "pix"}, "invalid_request"),
    ("outra", order_data(), {"pedido_id": 101, "metodo": "pix"}, "not_found"),
    ("compra", None, {"pedido_id": 101, "metodo": "pix"}, "not_found"),
    ("compra", order_data(status="cancelado"), {"pedido_id": 101, "metodo": "pix"}, "invalid_request"),
    ("compra", order_data(total=-1), {"pedido_id": 101, "metodo": "pix"}, "invalid_state"),
    ("compra", order_data(), {"pedido_id": 101, "metodo": "pix", "valor": 1}, "invalid_request"),
])
async def test_payment_preconditions_before_generation(environment, monkeypatch, session, order, body, expected):
    engine, sessions, logger = environment
    if order is not None:
        await sessions.save_session("compra", {"pedidos": {"101": order}})
    calls = mock_responses(monkeypatch, engine, [])
    result = await engine.simulate("/pagamentos", "POST", request_body=body, session_id=session)
    assert result.failure.kind.value == expected
    assert not calls
    state = await sessions.get_session("compra") or {}
    assert "pagamentos" not in state
