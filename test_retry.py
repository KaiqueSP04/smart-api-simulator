import asyncio

from app.application.context_builder import ContextBuilder
from app.application.response_generation import ResponseGenerationService
from app.application.session_resources import SessionResources
from app.application.simulation_engine import SimulationEngine
from app.models import Endpoint
from app.application.validator import PayloadValidator


class FakeSessionStore:
    async def initialize(self):
        pass

    async def get_session(self, session_id):
        return None

    async def save_session(self, session_id, state):
        pass


class FakeResponseGenerator:
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

    fake_generator = FakeResponseGenerator()
    session_resources = SessionResources(FakeSessionStore())
    validator = PayloadValidator()
    engine = SimulationEngine(
        endpoints=[endpoint],
        context_builder=ContextBuilder({}),
        session_resources=session_resources,
        response_generation=ResponseGenerationService(
            fake_generator,
            validator,
            session_resources,
        ),
        validator=validator,
    )

    result = await engine.simulate("/products", "GET")

    print("Tentativas:", fake_generator.attempts)
    print("Resultado:", result)


asyncio.run(main())