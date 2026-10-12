import asyncio
from app.main import engine


async def testar():
    sessao = "testeconsistencia001"

    pedido_original = {
        "id": 101,
        "customer_name": "Teste Integridade",
        "total": 175,
        "status": "created"
    }

    await engine.session_manager.save_session(
        sessao,
        {"orders": {"101": pedido_original.copy()}}
    )

    async def resposta_inconsistente(context):
        return {
            "id": 101,
            "customer_name": "Teste Integridade",
            "total": 9999,
            "status": "cancelled"
        }

    original = engine.generate_response

    try:
        engine.generate_response = resposta_inconsistente

        resultado = await engine.simulate(
            path="/orders/{id}/cancel",
            method="POST",
            parameters={"id": "101"},
            session_id=sessao
        )

        estado = await engine.session_manager.get_session(sessao)
        pedido_final = estado["orders"]["101"]

        print("HTTP:", resultado["status_code"])
        print("Valor original:", pedido_original["total"])
        print("Valor armazenado:", pedido_final["total"])
        print("Status armazenado:", pedido_final["status"])
        print("Valor preservado:", pedido_final["total"] == 175)

        print("Valor retornado pela API:", resultado.get("data", {}).get("total"))
        print("Valor armazenado no banco:", pedido_final["total"])
        print(
            "Resposta consistente com o banco:",
            resultado.get("data", {}).get("total") == pedido_final["total"]
        )

    finally:
        engine.generate_response = original


asyncio.run(testar())