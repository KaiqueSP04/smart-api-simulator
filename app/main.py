import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from pymongo import AsyncMongoClient

from .adapters.gemini import GeminiResponseGenerator
from .adapters.http_api import create_http_app
from .adapters.mongodb_request_logger import RequestLogger
from .adapters.mongodb_sessions import SessionManager
from .adapters.openapi_parser import get_endpoints, parse_openapi
from .application.context_builder import ContextBuilder
from .application.response_generation import ResponseGenerationService
from .application.session_resources import SessionResources
from .application.simulation_engine import SimulationEngine
from .application.validator import PayloadValidator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def create_app():
    contract = parse_openapi(
        str(PROJECT_ROOT / "contracts" / "test-api.yaml")
    )
    endpoints = get_endpoints(contract)

    mongo_client = AsyncMongoClient(os.getenv("MONGODB_URI"))
    database = mongo_client["smart_api_simulator"]

    session_store = SessionManager(database)
    session_resources = SessionResources(session_store)
    request_log = RequestLogger(database)
    response_generator = GeminiResponseGenerator()
    validator = PayloadValidator()
    context_builder = ContextBuilder(contract)
    response_generation = ResponseGenerationService(
        response_generator,
        validator,
        session_resources,
    )
    simulation_engine = SimulationEngine(
        endpoints=endpoints,
        context_builder=context_builder,
        session_resources=session_resources,
        response_generation=response_generation,
        validator=validator,
        request_logger=request_log,
    )

    @asynccontextmanager
    async def lifespan(_app):
        try:
            await mongo_client.admin.command("ping")
            await session_store.initialize()
            yield
        finally:
            await mongo_client.close()

    return create_http_app(endpoints, simulation_engine, lifespan)


app = create_app()
