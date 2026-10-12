import inspect
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Body, Header
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient

from .parser import parse_openapi, get_endpoints
from .simulation_engine import SimulationEngine
from .session_manager import SessionManager
from .request_logger import RequestLogger


load_dotenv()


contract = parse_openapi("contracts/test-api.yaml")
endpoints = get_endpoints(contract)

mongo_client = AsyncMongoClient(
    os.getenv("MONGODB_URI")
)

db = mongo_client["smart_api_simulator"]

session_manager = SessionManager(db)
request_logger = RequestLogger(db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo_client.admin.command("ping")
    await session_manager.initialize()

    yield

    await mongo_client.close()


app = FastAPI(
    title="Smart API Simulator",
    version="0.1.0",
    lifespan=lifespan
)


engine = SimulationEngine(
    endpoints,
    contract,
    session_manager,
    request_logger
)


@app.get("/")
def root():
    return {
        "message": "Smart API Simulator funcionando!"
    }


def get_python_type(schema: dict):
    schema_type = schema.get("type")

    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool
    }

    return type_mapping.get(schema_type, str)


def create_endpoint_handler(endpoint):
    async def endpoint_handler(
        request: Request,
        x_session_id: str | None = None,
        **kwargs
    ):
        parameters = {
            **request.path_params,
            **dict(request.query_params)
        }

        request_body = kwargs.get("body")

        session_id = x_session_id

        result = await engine.simulate(
            endpoint.path,
            endpoint.method,
            parameters,
            request_body,
            session_id
        )

        return JSONResponse(
            status_code=result.get("status_code", 200),
            content=result
        )

    signature_parameters = [
        inspect.Parameter(
            "request",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request
        )
    ]

    for parameter in endpoint.parameters:
        if parameter.location not in {"path", "query"}:
            continue

        parameter_type = get_python_type(
            parameter.schema_data
        )

        if parameter.required:
            default = inspect.Parameter.empty
        else:
            default = None

        signature_parameter = inspect.Parameter(
            parameter.name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=parameter_type,
            default=default
        )

        signature_parameters.append(
            signature_parameter
        )

    if endpoint.request_body:
        signature_parameters.append(
            inspect.Parameter(
                "body",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict,
                default=Body(...)
            )
        )

    signature_parameters.append(
        inspect.Parameter(
            "x_session_id",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=str | None,
            default=Header(
                None,
                alias="X-Session-ID"
            )
        )
    )

    endpoint_handler.__signature__ = inspect.Signature(
        parameters=signature_parameters
    )

    return endpoint_handler


def register_endpoint(endpoint):
    endpoint_handler = create_endpoint_handler(endpoint)

    documented_responses = {
        200: {"description": "Operação realizada com sucesso"},
        201: {"description": "Recurso criado com sucesso"},
        400: {"description": "Requisição inválida"},
        404: {"description": "Recurso não encontrado"},
        429: {"description": "Limite de requisições do serviço de IA"},
        503: {"description": "Serviço temporariamente indisponível"}
    }

    app.add_api_route(
        endpoint.path,
        endpoint_handler,
        methods=[endpoint.method],
        responses=documented_responses
    )


for endpoint in endpoints:
    register_endpoint(endpoint)