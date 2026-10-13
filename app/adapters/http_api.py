import inspect

from fastapi import Body, FastAPI, Header, Path, Query, Request
from fastapi.responses import JSONResponse

from ..models import Endpoint
from .http_results import to_http_response
from .swagger_docs import DESCRIPTION, documented_responses, resource_tag
from ..application.simulation_engine import SimulationEngine


def get_python_type(schema: dict):
    schema_type = schema.get("type")

    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }

    return type_mapping.get(schema_type, str)


def create_endpoint_handler(endpoint: Endpoint, engine: SimulationEngine):
    async def endpoint_handler(
        request: Request,
        x_session_id: str | None = None,
        **kwargs,
    ):
        parameters = {
            **request.path_params,
            **dict(request.query_params),
        }
        request_body = kwargs.get("body")

        result = await engine.simulate(
            endpoint.path,
            endpoint.method,
            parameters,
            request_body,
            x_session_id,
        )

        status_code, content = to_http_response(result)
        return JSONResponse(status_code=status_code, content=content)

    signature_parameters = [
        inspect.Parameter(
            "request",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request,
        )
    ]

    for parameter in endpoint.parameters:
        if parameter.location not in {"path", "query"}:
            continue

        parameter_type = get_python_type(parameter.schema_data)
        parameter_default = ... if parameter.required else None
        parameter_options = {
            "default": parameter_default,
            "description": parameter.description,
        }
        if parameter.example is not None:
            parameter_options["openapi_examples"] = {
                "example": {
                    "summary": parameter.description or "Exemplo de valor",
                    "value": parameter.example,
                }
            }

        if parameter.location == "path":
            fastapi_default = Path(**parameter_options)
        else:
            fastapi_default = Query(**parameter_options)

        signature_parameters.append(
            inspect.Parameter(
                parameter.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=parameter_type,
                default=fastapi_default,
            )
        )

    if endpoint.request_body:
        signature_parameters.append(
            inspect.Parameter(
                "body",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict,
                default=Body(
                    ... if endpoint.request_body.get("required", True) else None,
                    description=endpoint.request_body.get("description"),
                ),
            )
        )

    signature_parameters.append(
        inspect.Parameter(
            "x_session_id",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=str | None,
            default=Header(
                None,
                alias="X-Session-ID",
                description=(
                    "Opcional. Preencha, por exemplo, checkout-demo-001 e repita "
                    "esse valor em cada chamada do fluxo. Sem ele, os recursos "
                    "não são mantidos entre requisições."
                ),
                openapi_examples={
                    "example": {
                        "summary": "Identificador da sessão de checkout",
                        "value": "checkout-demo-001",
                    }
                },
            ),
        )
    )

    endpoint_handler.__signature__ = inspect.Signature(
        parameters=signature_parameters
    )
    return endpoint_handler


def create_http_app(endpoints, engine: SimulationEngine, lifespan):
    app = FastAPI(
        title="Smart API Simulator",
        version="0.1.0",
        description=DESCRIPTION,
        openapi_tags=[
            {"name": "Pedidos", "description": "Crie um pedido, copie data.id e consulte ou cancele na mesma sessão."},
            {"name": "Pagamentos", "description": "Use o ID do pedido em order_id. O data.id do pagamento serve para consultar, confirmar ou cancelar."},
            {"name": "Sistema", "description": "Verifique se a API está disponível."},
        ],
        swagger_ui_parameters={
            "docExpansion": "none",
            "filter": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": -1,
        },
        lifespan=lifespan,
    )
    app.state.simulation_engine = engine

    @app.get("/", tags=["Sistema"], summary="Verifica se a API está disponível")
    def root():
        return {
            "message": "Smart API Simulator funcionando!"
        }

    for endpoint in endpoints:
        route_options = {}
        if endpoint.request_body:
            route_options["openapi_extra"] = {
                "requestBody": endpoint.request_body
            }

        app.add_api_route(
            endpoint.path,
            create_endpoint_handler(endpoint, engine),
            methods=[endpoint.method],
            status_code=int(next(iter(endpoint.responses))),
            responses=documented_responses(endpoint),
            summary=endpoint.summary,
            description=endpoint.description,
            tags=[resource_tag(endpoint)],
            **route_options,
        )

    return app
