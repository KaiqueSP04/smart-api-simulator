import json

from .models import Endpoint
from .validator import PayloadValidator
from .context_builder import ContextBuilder
from .session_manager import SessionManager
from .llm_adapter import LLMAdapter, GeminiTimeout

class SimulationEngine:
    def __init__(
        self,
        endpoints: list[Endpoint],
        contract: dict,
        session_manager: SessionManager
    ):
        self.endpoints = endpoints
        self.session_manager = session_manager
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

    def _get_resource_type(self, path: str):
        segments = [
            segment
            for segment in path.split("/")
            if segment and not segment.startswith("{")
        ]

        if not segments:
            return None

        return segments[0]

    async def _persist_state(
        self,
        session_id: str,
        path: str,
        response_data: dict
    ):
        if not isinstance(response_data, dict):
            return

        resource_type = self._get_resource_type(path)

        if resource_type is None:
            return

        entity_id = response_data.get("id")

        if entity_id is None:
            return

        state = await self.session_manager.get_session(session_id)

        if not isinstance(state, dict):
            state = {}

        resource_state = state.get(resource_type)

        if not isinstance(resource_state, dict):
            resource_state = {}

        resource_state[str(entity_id)] = response_data
        state[resource_type] = resource_state

        await self.session_manager.save_session(session_id, state)

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

            except GeminiTimeout:
                return {
                    "status_code": 503,
                    "message": "Gemini excedeu o tempo limite"
                }

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

        if session_id:
            await self._persist_state(
                session_id,
                path,
                response_data
            )

        return {
            "status_code": status_code,
            "data": response_data,
            "parameters": parameters or {},
            "request_body": request_body,
            "context": context
        }
