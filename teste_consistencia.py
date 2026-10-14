import asyncio
import json
from app.main import app
from app.adapters.http_results import to_http_response


engine = app.state.simulation_engine


async def testar():
    sessao = "testeconsistencia001"

    pedido_original = {
        "id": 101,
        "nome_cliente": "Teste Integridade",
        "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        "total": 175,
        "situacao": "criado"
    }

    await engine.session_resources.session_store.save_session(
        sessao,
        {"pedidos": {"101": pedido_original.copy()}}
    )

    async def resposta_inconsistente(context):
        return {
            "id": 101,
            "nome_cliente": "Teste Integridade",
            "itens": pedido_original["itens"],
            "total": 9999,
            "situacao": "cancelado"
        }

    original = engine.response_generation.response_generator.generate

    try:
        async def resposta_json(context):
            return json.dumps(await resposta_inconsistente(context))

        engine.response_generation.response_generator.generate = resposta_json

        resultado = await engine.simulate(
            path="/pedidos/{id}/cancelar",
            method="POST",
            parameters={"id": "101"},
            session_id=sessao
        )

        estado = await engine.session_resources.session_store.get_session(sessao)
        pedido_final = estado["pedidos"]["101"]

        print("HTTP:", to_http_response(resultado)[0])
        print("Valor original:", pedido_original["total"])
        print("Valor armazenado:", pedido_final["total"])
        print("Situação armazenada:", pedido_final["situacao"])
        print("Valor preservado:", pedido_final["total"] == 175)

        print("Valor retornado pela API:", (resultado.data or {}).get("total"))
        print("Valor armazenado no banco:", pedido_final["total"])
        print(
            "Resposta consistente com o banco:",
            (resultado.data or {}).get("total") == pedido_final["total"]
        )

    finally:
        engine.response_generation.response_generator.generate = original


asyncio.run(testar())
