import asyncio
import os

from dotenv import load_dotenv
from pymongo import AsyncMongoClient

from app.adapters.mongodb_sessions import SessionManager


async def main():
    load_dotenv()

    client = AsyncMongoClient(os.getenv("MONGODB_URI"))

    try:
        await client.admin.command("ping")
        print("MongoDB conectado")

        db = client["smart_api_simulator"]
        session_manager = SessionManager(db)
        await session_manager.initialize()

        session_id = "teste-session-manager"

        # 1. Salvar
        estado_inicial = {
            "order_id": "ORD-001",
            "status": "created"
        }

        await session_manager.save_session(
            session_id,
            estado_inicial
        )
        print("1. Sessão salva")

        # 2. Recuperar
        session = await session_manager.get_session(session_id)
        print("2. Sessão recuperada:", session)

        # 3. Atualizar
        estado_atualizado = {
            "order_id": "ORD-001",
            "status": "paid"
        }

        await session_manager.save_session(
            session_id,
            estado_atualizado
        )
        print("3. Sessão atualizada")

        # 4. Recuperar novamente
        session = await session_manager.get_session(session_id)
        print("4. Sessão após atualização:", session)

        # 5. Deletar
        await session_manager.delete_session(session_id)
        print("5. Sessão deletada")

        # 6. Confirmar que não existe mais
        session = await session_manager.get_session(session_id)
        print("6. Sessão após deleção:", session)

    finally:
        await client.close()


asyncio.run(main())