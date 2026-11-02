
"""Experimento de integração com Gemini e medição de desempenho."""

import asyncio
import csv
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.adapters.openapi_parser import get_endpoints, parse_openapi
from app.application.context_builder import ContextBuilder
from app.application.payment_rules import CommerceRules
from app.application.response_generation import ResponseGenerationService
from app.application.session_resources import SessionResources
from app.application.simulation_engine import SimulationEngine
from app.application.validator import PayloadValidator
from app.main import GeminiResponseGenerator


class StoreMemoria:
    def __init__(self):
        self.sessoes = {}

    async def get_session(self, session_id):
        return self.sessoes.get(session_id)

    async def save_session(self, session_id, state):
        self.sessoes[session_id] = state


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("AVISO: GEMINI_API_KEY nao encontrada no ambiente.")

    contract = parse_openapi(str(ROOT / "contracts" / "test-api.yaml"))
    resources = SessionResources(StoreMemoria())
    validator = PayloadValidator()
    rules = CommerceRules()

    engine = SimulationEngine(
        endpoints=get_endpoints(contract),
        context_builder=ContextBuilder(contract),
        session_resources=resources,
        response_generation=ResponseGenerationService(
            GeminiResponseGenerator(),
            validator,
            resources,
            normalizer=rules,
        ),
        validator=validator,
        request_policy=rules,
    )

    session = "experimento-gemini-local"
    pedido_id = None
    pagamento_id = None
    resultados = []

    async def executar(nome, path, method, params, body, esperado):
        inicio = time.perf_counter()

        try:
            result = await engine.simulate(
                path,
                method,
                parameters=params,
                request_body=body,
                session_id=session,
            )

            tempo_ms = (time.perf_counter() - inicio) * 1000

            if result.failure is not None:
                erro = str(result.failure)
                print(f"[FALHA] {nome} - {tempo_ms:.2f} ms - {erro}")
                resultados.append([nome, tempo_ms, False, erro])
                return None

            dados = result.data

            if not isinstance(dados, dict):
                erro = f"Resposta inesperada: {type(dados).__name__}"
                print(f"[FALHA] {nome} - {erro}")
                resultados.append([nome, tempo_ms, False, erro])
                return None

            situacao = dados.get("situacao")
            aprovado = situacao == esperado

            if aprovado:
                print(f"[OK] {nome} - {tempo_ms:.2f} ms")
                erro = ""
            else:
                erro = f"Situacao {situacao!r}, esperado {esperado!r}"
                print(f"[FALHA] {nome} - {tempo_ms:.2f} ms - {erro}")

            resultados.append([nome, tempo_ms, aprovado, erro])
            return dados if aprovado else None

        except Exception as exc:
            tempo_ms = (time.perf_counter() - inicio) * 1000
            erro = f"{type(exc).__name__}: {exc}"
            print(f"[ERRO] {nome} - {tempo_ms:.2f} ms - {erro}")
            resultados.append([nome, tempo_ms, False, erro])
            return None

    pedido = await executar(
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
    )

    if pedido is not None:
        pedido_id = pedido.get("id")

    if pedido_id is not None:
        await executar(
            "Consultar pedido",
            "/pedidos/{id}",
            "GET",
            {"id": pedido_id},
            None,
            "criado",
        )

        pagamento = await executar(
            "Criar pagamento",
            "/pagamentos",
            "POST",
            {},
            {"pedido_id": pedido_id, "metodo": "pix"},
            "pendente",
        )

        if pagamento is not None:
            pagamento_id = pagamento.get("id")

        if pagamento_id is not None:
            await executar(
                "Confirmar pagamento",
                "/pagamentos/{id}/confirmar",
                "POST",
                {"id": pagamento_id},
                None,
                "confirmado",
            )

            await executar(
                "Consultar pagamento",
                "/pagamentos/{id}",
                "GET",
                {"id": pagamento_id},
                None,
                "confirmado",
            )

            await executar(
                "Cancelar pagamento",
                "/pagamentos/{id}/cancelar",
                "POST",
                {"id": pagamento_id},
                None,
                "cancelado",
            )

        await executar(
            "Cancelar pedido",
            "/pedidos/{id}/cancelar",
            "POST",
            {"id": pedido_id},
            None,
            "cancelado",
        )

        await executar(
            "Consultar pedido cancelado",
            "/pedidos/{id}",
            "GET",
            {"id": pedido_id},
            None,
            "cancelado",
        )

        if pagamento_id is not None:
            await executar(
                "Consultar pagamento cancelado",
                "/pagamentos/{id}",
                "GET",
                {"id": pagamento_id},
                None,
                "cancelado",
            )

    destino = ROOT / "experimento" / "resultados_gemini.csv"

    with destino.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["operacao", "tempo_ms", "aprovado", "erro"]
        )
        escritor.writerows(resultados)

    tempos = [linha[1] for linha in resultados]
    aprovados = sum(1 for linha in resultados if linha[2])

    print()
    print("=== RESULTADOS DO GEMINI ===")
    print(f"Operacoes executadas: {len(resultados)}/9")
    print(f"Operacoes aprovadas: {aprovados}/{len(resultados)}")

    if tempos:
        print(f"Tempo medio: {statistics.mean(tempos):.2f} ms")
        print(f"Mediana: {statistics.median(tempos):.2f} ms")
        print(f"Tempo minimo: {min(tempos):.2f} ms")
        print(f"Tempo maximo: {max(tempos):.2f} ms")
        print(f"Tempo total: {sum(tempos):.2f} ms")

    print(f"CSV salvo em: {destino}")


if __name__ == "__main__":
    asyncio.run(main())
