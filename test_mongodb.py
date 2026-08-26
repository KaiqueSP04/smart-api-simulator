# TEMPORÁRIO: teste de conexão com MongoDB Atlas. Remover após o teste.

import asyncio
import os

from dotenv import load_dotenv
from pymongo import AsyncMongoClient


load_dotenv()

uri = os.getenv("MONGODB_URI")


async def main():
    client = AsyncMongoClient(uri)

    try:
        await client.admin.command("ping")
        print("CONEXAO COM MONGODB ATLAS OK")
    finally:
        await client.close()


asyncio.run(main())