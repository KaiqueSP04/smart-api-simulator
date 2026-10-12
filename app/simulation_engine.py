import json
import time

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
        session_manager: SessionManager,
        request_logger=None
    ):
        self.endpoints = endpoints
        self.session_manager = session_manager
        self.request_logger = request_logger
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

        existing_data = resource_state.get(str(entity_id), {})

        if isinstance(existing_data, dict) and existing_data:
            updated_data = existing_data.copy()

            if "status" in response_data:
                updated_data["status"] = response_data["status"]

            resource_state[str(entity_id)] = updated_data
        else:
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
        # Envolve a simulação para medir a latência e registrar o histórico
        # da requisição (coleção 'requests'), sem alterar a lógica central.
        inicio = time.perf_counter()

        result = await self._run(
            path,
            method,
            parameters,
            request_body,
            session_id
        )

        latency_ms = (time.perf_counter() - inicio) * 1000

        if self.request_logger is not None:
            await self.request_logger.log(
                path=path,
                method=method,
                status_code=result.get("status_code", 200),
                latency_ms=round(latency_ms, 2),
                valid=("data" in result),
                fallback=result.get("fallback", False),
                session_id=session_id
            )

        return result

    async def _run(
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

        method_upper = method.upper()
        path_parts = [part for part in path.split("/") if part]

        if (
            session_id
            and method_upper in {"GET", "POST"}
            and len(path_parts) >= 2
            and path_parts[1] == "{id}"
        ):
            resource_type = path_parts[0]
            entity_id = (parameters or {}).get("id")

            state = await self.session_manager.get_session(session_id)
            resources = (state or {}).get(resource_type, {})

            if str(entity_id) not in resources:
                return {
                    "status_code": 404,
                    "message": "Recurso não encontrado na sessão"
                }

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

        resource_type = self._get_resource_type(path)

        # Consultas de recursos existentes em uma sessão usam o estado
        # persistido como fonte de verdade, sem chamar a LLM.
        if session_id and method_upper == "GET" and "{id}" in path:
            entity_id = (parameters or {}).get("id")
            current_state = await self.session_manager.get_session(session_id)
            stored_data = (
                (current_state or {})
                .get(resource_type, {})
                .get(str(entity_id))
            )

            if not isinstance(stored_data, dict):
                return {
                    "status_code": 404,
                    "message": "Recurso não encontrado na sessão"
                }

            if response_schema and not self.validator.validate(
                stored_data, response_schema
            ):
                return {
                    "status_code": 503,
                    "message": "Estado armazenado incompatível com o schema da resposta"
                }

            return {
                "status_code": status_code,
                "data": stored_data,
                "parameters": parameters or {},
                "request_body": request_body,
                "context": context
            }

        response_data = None

        is_creation = (
            method.upper() == "POST"
            and path.rstrip("/") == f"/{resource_type}"
        )

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
                    response_data = None
                    continue

            if "{id}" in path and isinstance(response_data, dict):
                requested_id = (parameters or {}).get("id")
                returned_id = response_data.get("id")

                if returned_id is None or str(returned_id) != str(requested_id):
                    response_data = None
                    continue    

            if session_id and is_creation and isinstance(response_data, dict):
                entity_id = response_data.get("id")

                if entity_id is None:
                    response_data = None
                    continue

                state = await self.session_manager.get_session(session_id)
                resources = (state or {}).get(resource_type, {})

                if str(entity_id) in resources:
                    response_data = None
                    continue

            break

        if response_data is None:
            if is_creation:
                return {
                    "status_code": 503,
                    "message": "Não foi possível gerar um recurso válido e único após 3 tentativas"
                }

            return {
                "status_code": 503,
                "message": "Não foi possível gerar uma resposta válida após 3 tentativas"
            }

        if session_id and method_upper != "GET":
            await self._persist_state(
                session_id,
                path,
                response_data
            )

            if not is_creation and isinstance(response_data, dict):
                entity_id = response_data.get("id")

                if entity_id is not None:
                    updated_state = await self.session_manager.get_session(session_id)
                    stored_data = (
                        (updated_state or {})
                        .get(resource_type, {})
                        .get(str(entity_id))
                    )

                    if isinstance(stored_data, dict):
                        response_data = stored_data

        return {
            "status_code": status_code,
            "data": response_data,
            "parameters": parameters or {},
            "request_body": request_body,
            "context": context
        }
