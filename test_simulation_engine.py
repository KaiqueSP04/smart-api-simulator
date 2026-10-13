import asyncio

from app.application.simulation_engine import SimulationEngine
from app.models import Endpoint
from app.application.context_builder import ContextBuilder
from app.application.response_generation import ResponseGenerationService
from app.application.session_resources import SessionResources
from app.application.validator import PayloadValidator


class FakeSessionStore:
    async def initialize(self):
        pass

    async def get_session(self, session_id):
        return None

    async def save_session(self, session_id, state):
        pass


class FakeResponseGenerator:
    async def generate(self, context):
        return '{"id": 1, "name": "Mouse", "price": 150}'


def test_simulation_engine_uses_injected_response_generator():
    endpoint = Endpoint(
        path="/products",
        method="GET",
        responses={
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["id", "name", "price"],
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                            },
                        }
                    }
                }
            }
        },
    )
    session_resources = SessionResources(FakeSessionStore())
    validator = PayloadValidator()
    engine = SimulationEngine(
        endpoints=[endpoint],
        context_builder=ContextBuilder({}),
        session_resources=session_resources,
        response_generation=ResponseGenerationService(
            FakeResponseGenerator(),
            validator,
            session_resources,
        ),
        validator=validator,
    )

    result = asyncio.run(engine.simulate("/products", "GET"))

    assert result.failure is None
    assert result.response_key == "200"
    assert result.data["id"] == 1
