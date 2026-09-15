import asyncio
import os

from dotenv import load_dotenv
from pymongo import AsyncMongoClient

from app.session_manager import SessionManager


load_dotenv()


async def main():
    mongo_client = AsyncMongoClient(
        os.getenv("MONGODB_URI")
    )

    db = mongo_client["smart_api_simulator"]

    session_manager = SessionManager(db)

    await mongo_client.admin.command("ping")

    await session_manager.save_session(
        "teste-001",
        {
            "order_id": "ORD-001",
            "status": "created"
        }
    )

    print("Sessão teste-001 salva.")

    await mongo_client.close()


asyncio.run(main())