import asyncio
import json
from app.main import app
from app.adapters.http_results import to_http_response


engine = app.state.simulation_engine


async def testar():
    sessao = "testeconsulta001"

    pedido_original = {
        "id": 101,
        "nome_cliente": "Teste Consulta",
        "itens": [{"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 175}],
        "total": 175,
        "situacao": "criado"
    }

    await engine.session_resources.session_store.save_session(
        sessao,
        {"pedidos": {"101": pedido_original.copy()}}
    )

    chamadas = 0

    async def resposta_inconsistente(context):
        nonlocal chamadas
        chamadas += 1

        return {
            "id": 101,
            "nome_cliente": "Teste Consulta",
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
            path="/pedidos/{id}",
            method="GET",
            parameters={"id": "101"},
            session_id=sessao
        )

        estado = await engine.session_resources.session_store.get_session(sessao)
        pedido_armazenado = estado["pedidos"]["101"]
        dados_retornados = resultado.data or {}

        print("Tentativas:", chamadas)
        print("HTTP:", to_http_response(resultado)[0])
        print("Valor armazenado:", pedido_armazenado["total"])
        print("Valor retornado:", dados_retornados.get("total"))
        print("Situação armazenada:", pedido_armazenado["situacao"])
        print("Situação retornada:", dados_retornados.get("situacao"))
        print("Banco preservado:", pedido_armazenado == pedido_original)
        print("Resposta consistente:", dados_retornados == pedido_armazenado)

    finally:
        engine.response_generation.response_generator.generate = original


asyncio.run(testar())
