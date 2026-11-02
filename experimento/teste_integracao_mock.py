
"""Teste integrado do mock com medição de desempenho."""

import asyncio
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adapters.openapi_parser import get_endpoints, parse_openapi
from app.application.context_builder import ContextBuilder
from app.application.payment_rules import CommerceRules
from app.application.response_generation import ResponseGenerationService
from app.application.session_resources import SessionResources
from app.application.simulation_engine import SimulationEngine
from app.application.validator import PayloadValidator
from experimento.mock_tradicional import MockTradicional


class StoreMemoria:
    def __init__(self):
        self.sessoes = {}

    async def get_session(self, session_id):
        return self.sessoes.get(session_id)

    async def save_session(self, session_id, state):
        self.sessoes[session_id] = state


async def main():
    contract = parse_openapi(
        str(ROOT / "contracts" / "test-api.yaml")
    )

    resources = SessionResources(StoreMemoria())
    validator = PayloadValidator()
    rules = CommerceRules()

    engine = SimulationEngine(
        endpoints=get_endpoints(contract),
        context_builder=ContextBuilder(contract),
        session_resources=resources,
        response_generation=ResponseGenerationService(
            MockTradicional(),
            validator,
            resources,
            normalizer=rules,
        ),
        validator=validator,
        request_policy=rules,
    )

    session = "experimento-mock-local"

    passos = [
        (
            "Criar pedido",
            "/pedidos",
            "POST",
            {},
            {
                "nome_cliente": "Teste TCC",
                "itens": [
                    {
                        "nome_produto": "Mouse",
                        "quantidade": 2,
                        "preco_unitario": 75.0,
                    }
                ],
            },
            "criado",
        ),
        (
            "Consultar pedido",
            "/pedidos/{id}",
            "GET",
            {"id": 1},
            None,
            "criado",
        ),
        (
            "Criar pagamento",
            "/pagamentos",
            "POST",
            {},
            {"pedido_id": 1, "metodo": "pix"},
            "pendente",
        ),
        (
            "Confirmar pagamento",
            "/pagamentos/{id}/confirmar",
            "POST",
            {"id": 1},
            None,
            "confirmado",
        ),
        (
            "Consultar pagamento",
            "/pagamentos/{id}",
            "GET",
            {"id": 1},
            None,
            "confirmado",
        ),
        (
            "Cancelar pagamento",
            "/pagamentos/{id}/cancelar",
            "POST",
            {"id": 1},
            None,
            "cancelado",
        ),
        (
            "Cancelar pedido",
            "/pedidos/{id}/cancelar",
            "POST",
            {"id": 1},
            None,
            "cancelado",
        ),
        (
            "Consultar pedido cancelado",
            "/pedidos/{id}",
            "GET",
            {"id": 1},
            None,
            "cancelado",
        ),
        (
            "Consultar pagamento cancelado",
            "/pagamentos/{id}",
            "GET",
            {"id": 1},
            None,
            "cancelado",
        ),
    ]

    tempos = []

    for nome, path, method, params, body, situacao in passos:
        inicio = time.perf_counter()

        result = await engine.simulate(
            path,
            method,
            parameters=params,
            request_body=body,
            session_id=session,
        )

        tempo_ms = (time.perf_counter() - inicio) * 1000
        tempos.append(tempo_ms)

        if result.failure is not None:
            raise AssertionError(
                f"{nome}: {result.failure}"
            )

        if result.data["situacao"] != situacao:
            raise AssertionError(
                f"{nome}: situacao "
                f"{result.data['situacao']!r} != {situacao!r}"
            )

        print(f"[OK] {nome} - {tempo_ms:.2f} ms")

    print()
    print(f"Resultado: {len(passos)}/{len(passos)} aprovados")
    print()
    print("=== DESEMPENHO DO MOCK TRADICIONAL ===")
    print(f"Tempo medio: {statistics.mean(tempos):.2f} ms")
    print(f"Mediana: {statistics.median(tempos):.2f} ms")
    print(f"Tempo minimo: {min(tempos):.2f} ms")
    print(f"Tempo maximo: {max(tempos):.2f} ms")
    print(f"Tempo total: {sum(tempos):.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())
