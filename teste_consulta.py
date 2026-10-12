import asyncio
from app.main import engine


async def testar():
    sessao = "testeconsulta001"

    pedido_original = {
        "id": 101,
        "customer_name": "Teste Consulta",
        "total": 175,
        "status": "created"
    }

    await engine.session_manager.save_session(
        sessao,
        {"orders": {"101": pedido_original.copy()}}
    )

    chamadas = 0

    async def resposta_inconsistente(context):
        nonlocal chamadas
        chamadas += 1

        return {
            "id": 101,
            "customer_name": "Teste Consulta",
            "total": 9999,
            "status": "cancelled"
        }

    original = engine.generate_response

    try:
        engine.generate_response = resposta_inconsistente

        resultado = await engine.simulate(
            path="/orders/{id}",
            method="GET",
            parameters={"id": "101"},
            session_id=sessao
        )

        estado = await engine.session_manager.get_session(sessao)
        pedido_armazenado = estado["orders"]["101"]
        dados_retornados = resultado.get("data", {})

        print("Tentativas:", chamadas)
        print("HTTP:", resultado["status_code"])
        print("Valor armazenado:", pedido_armazenado["total"])
        print("Valor retornado:", dados_retornados.get("total"))
        print("Status armazenado:", pedido_armazenado["status"])
        print("Status retornado:", dados_retornados.get("status"))
        print("Banco preservado:", pedido_armazenado == pedido_original)
        print("Resposta consistente:", dados_retornados == pedido_armazenado)

    finally:
        engine.generate_response = original


asyncio.run(testar())