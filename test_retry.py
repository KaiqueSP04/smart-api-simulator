import asyncio

from app.simulation_engine import SimulationEngine
from app.models import Endpoint
from app.session_manager import SessionManager


class FakeLLMAdapter:
    def __init__(self):
        self.attempts = 0

    async def generate(self, context):
        self.attempts += 1

        if self.attempts == 1:
            return '{"id": "invalido", "name": "Mouse", "price": 150}'

        return '{"id": 1, "name": "Mouse", "price": 150}'


async def main():
    endpoint = Endpoint(
        path="/products",
        method="GET",
        responses={
            "200": {
                "description": "Produto",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["id", "name", "price"],
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "price": {"type": "number"}
                            }
                        }
                    }
                }
            }
        }
    )

    class FakeDB:
        def __getitem__(self, name):
            return None


    engine = SimulationEngine(
        [endpoint],
        {},
        SessionManager(FakeDB())
    )

    fake_llm = FakeLLMAdapter()
    engine.llm_adapter = fake_llm

    result = await engine.simulate("/products", "GET")

    print("Tentativas:", fake_llm.attempts)
    print("Resultado:", result)


asyncio.run(main())