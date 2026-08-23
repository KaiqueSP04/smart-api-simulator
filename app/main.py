import inspect

from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse
from .parser import parse_openapi, get_endpoints
from .simulation_engine import SimulationEngine


app = FastAPI(
    title="Smart API Simulator",
    version="0.1.0"
)


contract = parse_openapi("contracts/test-api.yaml")
endpoints = get_endpoints(contract)

engine = SimulationEngine(endpoints)


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
    async def endpoint_handler(request: Request, **kwargs):
        parameters = {
            **request.path_params,
            **dict(request.query_params)
        }

        request_body = kwargs.get("body")

        result = engine.simulate(
            endpoint.path,
            endpoint.method,
            parameters,
            request_body
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

        parameter_type = get_python_type(parameter.schema_data)

        signature_parameter = inspect.Parameter(
            parameter.name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=parameter_type
        )

        signature_parameters.append(signature_parameter)

    if endpoint.request_body:
        signature_parameters.append(
            inspect.Parameter(
                "body",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict,
                default=Body(...)
            )
        )

    endpoint_handler.__signature__ = inspect.Signature(
        parameters=signature_parameters
    )

    return endpoint_handler


def register_endpoint(endpoint):
    endpoint_handler = create_endpoint_handler(endpoint)

    app.add_api_route(
        endpoint.path,
        endpoint_handler,
        methods=[endpoint.method]
    )


for endpoint in endpoints:
    register_endpoint(endpoint)