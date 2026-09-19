import json

from .models import Endpoint
from .validator import PayloadValidator
from .context_builder import ContextBuilder
from .session_manager import SessionManager
from .llm_adapter import LLMAdapter


class SimulationEngine:
    def __init__(
        self,
        endpoints: list[Endpoint],
        contract: dict,
        session_manager: SessionManager
    ):
        self.endpoints = endpoints
        self.validator = PayloadValidator()
        self.context_builder = ContextBuilder(
            contract,
            session_manager
        )
        self.llm_adapter = LLMAdapter()

    def find_endpoint(self, path: str, method: str):
        for endpoint in self.endpoints:
            if (
                endpoint.path == path
                and endpoint.method.upper() == method.upper()
            ):
                return endpoint

        return None

    def get_response_schema(self, endpoint: Endpoint):
        if not endpoint.responses:
            return None

        response = endpoint.responses.get(
            str(next(iter(endpoint.responses)))
        )

        if not response:
            return None

        content = response.get("content", {})
        json_content = content.get("application/json", {})

        return json_content.get("schema")

    def get_request_body_schema(self, endpoint: Endpoint):
        if not endpoint.request_body:
            return None

        content = endpoint.request_body.get("content", {})
        json_content = content.get("application/json", {})

        return json_content.get("schema")

    async def generate_response(self, context):
        response_text = await self.llm_adapter.generate(context)

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None

    async def simulate(
        self,
        path: str,
        method: str,
        parameters=None,
        request_body=None,
        session_id: str | None = None
    ):
        endpoint = self.find_endpoint(path, method)

        if endpoint is None:
            return {
                "status_code": 404,
                "message": "Endpoint não encontrado"
            }

        context = await self.context_builder.build(
            endpoint,
            session_id,
            parameters,
            request_body
        )

        request_schema = self.get_request_body_schema(endpoint)

        if request_schema:
            if request_body is None:
                return {
                    "status_code": 400,
                    "message": "Request body obrigatório"
                }

            is_valid = self.validator.validate(
                request_body,
                request_schema
            )

            if not is_valid:
                return {
                    "status_code": 400,
                    "message": "Request body não corresponde ao schema"
                }

        status_code = int(next(iter(endpoint.responses)))
        response_schema = context.get("response_schema")

        response_data = None

        for _ in range(3):
            try:
                response_data = await self.generate_response(context)

            except Exception as exc:
                exception_name = type(exc).__name__
                exception_status = getattr(exc, "status_code", None)

                if exception_status == 429:
                    return {
                        "status_code": 429,
                        "message": "Limite de requisições do Gemini excedido"
                    }

                if exception_name == "APITimeoutError":
                    return {
                        "status_code": 503,
                        "message": "Gemini excedeu o tempo limite"
                    }

                return {
                    "status_code": 503,
                    "message": "Serviço do Gemini indisponível"
                }

            if response_data is None:
                continue

            if response_schema:
                is_valid = self.validator.validate(
                    response_data,
                    response_schema
                )

                if not is_valid:
                    continue

            break

        if response_data is None:
            return {
                "status_code": 500,
                "message": "Gemini retornou uma resposta inválida após 3 tentativas"
            }

        return {
            "status_code": status_code,
            "data": response_data,
            "parameters": parameters or {},
            "request_body": request_body,
            "context": context
        }